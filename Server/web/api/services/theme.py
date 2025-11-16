import json
from functools import partial
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import (RunnableLambda, RunnableParallel, RunnableSerializable, RunnableBranch)
from langchain_core.runnables.base import RunnableEach
from langchain_openai import ChatOpenAI
from langsmith import Client as LangSmithClient
from pydantic import BaseModel, Field
from selenium.webdriver.common.by import By
from langchain_community.tools import DuckDuckGoSearchRun, DuckDuckGoSearchResults

import api.configs as configs
import api.cruds as cruds
from api import utils
from api.core.common_service import CommonService
from api.logger import Logger
from api.utils.web_loader_chrome import WebLoaderChrome


class ThemeService(CommonService):
    """
    テーマ関連の処理を集約したサービスクラス
    """
    
    async def generate_axis(self, theme: str) -> list[str]:
        
        # 1. LCELのエントリーポイントになるデータ
        def get_state(args: dict) -> dict:
            return {
                "theme": args["theme"],
            }
        state = RunnableLambda(get_state) #callableで書く必要があるのでメソッドで定義

        search_runnable: RunnableLambda = RunnableLambda(self.run_duckduckgo)

        # 2. LCEL で直列化 処理は各チェイン内を参照
        full_chain = (state
            .assign(background_detail=search_runnable) 
            .assign(axis_list=self.get_axis_chain())
        )

        # 3. Chain実行
        result: list[str] = await full_chain.ainvoke({
            "theme": theme
        })
        
        result["axis_list"] = [text.lstrip('- ').strip() for text in result["axis_list"]]
        
        Logger.debug(result)
        
        return result
    
    def generate_comments_for_axis(self) -> RunnableSerializable:
        """
        単一の axis に対してコメント生成を行う LCEL チェーン（Runnable）を返す。
        - 入力: {"theme": str, "axis": str}
        - 出力: {"theme": str, "axis": str, "background_detail": str, "comments": list[str]}
        """
        # 1. LCELのエントリーポイントになるデータ
        def get_state(input_args: Dict[str, Any]) -> Dict[str, Any]:
            """
            チェーンの入力正規化。
            期待する入力キーのみを抜き出し、次段に渡す。
            """
            return {
                "theme": input_args["theme"],
                "axis": input_args["axis"],
            }

        state: RunnableLambda = RunnableLambda(get_state)  # callableで書く必要があるのでメソッドで定義

        # 2. 各種の前処理の準備（DuckDuckGo 検索）
        search_runnable: RunnableLambda = RunnableLambda(self.run_duckduckgo)

        # 3. LCEL で直列化（各チェイン内の処理は既存を利用）
        #    - background_detail はここで 1 回だけ取得
        #    - comments は get_comments_per_axis_chain に委譲
        #    - 最後にコメントの整形を行う（"- " の除去など）
        def postprocess_comments(output_state: Dict[str, Any]) -> Dict[str, Any]:
            """
            comments の前処理（先頭 "- " の除去など）を行いつつ、状態をそのまま返す。
            """
            processed_comments: List[str] = [
                single_text.lstrip("- ").strip() for single_text in output_state.get("comments", [])
            ]
            output_state = dict(output_state)
            output_state["comments"] = processed_comments
            return output_state

        full_chain: RunnableSerializable = (
            state
            .assign(background_detail=search_runnable)
            .assign(comments=self.get_comments_per_axis_chain())
            | RunnableLambda(postprocess_comments)
        )

        return full_chain

    async def generate_comments_for_axes(
        self,
        theme: str,
        axis_list: List[str],
        max_concurrency: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        複数の axis に対して「単一 axis 用チェーン」を abatch() で並列実行する。

        Args:
            theme (str): テーマ
            axis_list (List[str]): 対立軸のリスト
            max_concurrency (int): 同時実行数の上限（外部API呼び出し保護用）

        Returns:
            List[Dict[str, Any]]: 各 axis 分の結果。
                例: [{"theme": "...", "axis": "...", "background_detail": "...", "comments": [...]}, ...]
        """
        # 単一 axis 用チェーン（Runnable）を取得
        per_axis_runnable: RunnableSerializable = self.generate_comments_for_axis()

        # abatch の入力は「各要素が Runnable の入力になる dict」
        runnable_inputs: List[Dict[str, Any]] = [
            {"theme": theme, "axis": single_axis} for single_axis in axis_list
        ]

        # abatch で並列実行（順序は入力順を保持）
        results: List[Dict[str, Any]] = await per_axis_runnable.abatch(
            runnable_inputs,
            config={"max_concurrency": max_concurrency},
        )

        Logger.debug(results)
        
        comments = []
        for item in results:
            comments += item["comments"]

        return comments

    async def generate_description(self, theme: str, axis_list: List[str], comments: List[str]) -> str:
        
        # 1. LCELのエントリーポイントになるデータ
        def get_state(args: dict) -> dict:
            return {
                "theme": args["theme"],
                "axis": args["axis"],
                "comments": args["comments"],
            }
        state = RunnableLambda(get_state) #callableで書く必要があるのでメソッドで定義

        search_runnable: RunnableLambda = RunnableLambda(self.run_duckduckgo)

        # 2. LCEL で直列化 処理は各チェイン内を参照
        full_chain = (state
            .assign(background_detail=search_runnable) 
            .assign(description=self.get_description_chain())
        )

        # 3. Chain実行
        result: list[str] = await full_chain.ainvoke({
            "theme": theme,
            "axis": [f"- {axis}\n" for axis in axis_list],
            "comments": [f"- {comment}\n" for comment in comments],
        })
        
        Logger.debug(result)
        
        return result["description"]

    def run_duckduckgo(self, inputs: dict) -> str:
        """
        テーマに基づいてDuckDuckGo検索を実行し、概要を返す。
        """
        try:
            search_result = DuckDuckGoSearchResults(backend="news", output_format="list").run(inputs['theme'])
            
            output_lines = []
            for news_item in search_result:
                title = news_item.get("title", "").strip()
                snippet = news_item.get("snippet", "").strip()
                formatted_text = f"##{title}\n- {snippet}"
                output_lines.append(formatted_text)
            result_text = "\n\n".join(output_lines)
            
            Logger.debug(result_text)
        except Exception as e:
            return ""

        return result_text
    
    def get_theme_chain(self) -> RunnableSerializable:
        """
        テーマ生成用のLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model="gpt-5"), StrOutputParser()
        return  self.get_prompt_callable("get_theme") | llm | parser
    
    def get_axis_chain(self) -> RunnableSerializable:
        """
        対立軸生成用のLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model="gpt-5-nano", reasoning_effort="low", verbosity="low"), StrOutputParser()
        return  self.get_prompt_callable("get_axis_standalone") | llm | parser | RunnableLambda(lambda x: x.splitlines())
    
    def get_comments_per_axis_chain(self) -> RunnableSerializable:
        """
        対立軸ごとのコメント内容を取得するLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model="gpt-5-nano", reasoning_effort="low", verbosity="low"), StrOutputParser()
        comments_prompt = self.get_prompt_callable("get_comments_standalone")
        
        # 空白行はフィルターでカットして返却
        return (
            comments_prompt | llm | parser | RunnableLambda(lambda s: [item.strip() for item in s.splitlines() if item and item.strip()])
        )

    def get_comments_by_axis_chain(self) -> RunnableSerializable:
        """
        対立軸全てのコメント内容を一括取得するLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        
        def _explode_axes(data: Dict[str, Any]) -> List[Dict[str, Any]]:
            """axis_list を展開して、各 axis を埋め込んだ辞書のリストにする"""
            return [{**data, "axis": axis} for axis in data["axis_list"]]

        def _pick_axis(data: Dict[str, Any]) -> str:
            """辞書から axis の値だけ取り出す"""
            return data["axis"]

        def _pick_fields_for_comments(data: Dict[str, Any]) -> Dict[str, Any]:
            """コメント生成に必要なフィールドだけを抽出して渡す"""
            return {
                "page_title": data["page_title"],
                "main_tweet_text": data["main_tweet_text"],
                "reaction_text": data["reaction_text"],
                "detail": data["detail"],
                "theme": data["theme"],
                "axis": data["axis"],
            }

        def _aggregate_axis_to_comments(items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
            """[{axis, comments}] の配列を {axis: comments} の辞書にまとめる"""
            return {it["axis"]: it["comments"] for it in items}
        
        # 軸リストを展開（1軸ごとに {"base": {...}, "axis": str} に分解）
        explode_axes = RunnableLambda(_explode_axes)

        # 各軸に対して {"axis": str, "comments": list[str]} を生成
        one_axis_unit = RunnableParallel(
            axis=RunnableLambda(_pick_axis),
            comments=(
                RunnableLambda(_pick_fields_for_comments)
                | self.get_comments_per_axis_chain()
            ),
        )

        # すべての軸を map で処理し、最終的に {axis: comments[]} 辞書にまとめる
        return (
            explode_axes
            | one_axis_unit.map()
            | RunnableLambda(_aggregate_axis_to_comments)
        )

    def get_description_chain(self) -> RunnableSerializable:
        """
        テーマの説明を取得するLCELチェインを取得

        Returns:
            _type_: LCELチェイン
        """
        llm, parser = ChatOpenAI(model="gpt-5-nano", reasoning_effort="low", verbosity="low"), StrOutputParser()
        return (
            self.get_prompt_callable("get_description_standalone")
            | llm
            | parser
        )
    
    def get_category_chain(self) -> RunnableSerializable:
        """
        カテゴリの説明を取得するLCELチェインを取得

        Returns:
            _type_: LCELチェイン
        """
        # 構造化出力用のPydanticクラス
        class CategoryModel(BaseModel):
            category: int = Field(..., description="合致するテーマの番号")
            
        def _inject_format_instructions(data: Dict[str, Any], fmt: str) -> Dict[str, Any]:
            """入力辞書に format_instructions を追加"""
            new_data = {**data, "format_instructions": fmt}
            return new_data

        def _extract_category_int(model: CategoryModel) -> int:
            """CategoryModel から category(int) を抽出"""
            # Pydantic Modelのバリデーション後、整数を返す
            return int(model.category)

            
        llm = ChatOpenAI(model="gpt-5-nano")
        parser = PydanticOutputParser(pydantic_object=CategoryModel)
        # プロンプトに含めるフォーマット指示
        format_instructions = parser.get_format_instructions()
        prompt = self.get_prompt_callable("get_category")  # ← プロンプト側に {format_instructions} を含めておく

        return (
            RunnableLambda(partial(_inject_format_instructions, fmt=format_instructions))
            | prompt
            | llm
            | parser                       # → CategoryModel
            | RunnableLambda(_extract_category_int)  # → int にして出力
        )
    
    # ###########################################################################
    # 共通ユーティリティ処理
    # ###########################################################################

    def get_prompt_callable(self, key: str) -> RunnableLambda:
        """
        LangSmithからのプロンプト取得処理

        Args:
            key (str): プロンプト取得キー

        Returns:
            RunnableLambda: チェーン結合可能なラムダ形式で返却
        """
        return RunnableLambda(lambda _: LangSmithClient().pull_prompt(f"{key}"))