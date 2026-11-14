import re
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableSerializable
from langchain_openai import ChatOpenAI
from langsmith import Client as LangSmithClient
from langchain_community.tools import DuckDuckGoSearchResults

import api.configs as configs
from api.core.common_service import CommonService
from api.logger import Logger


class ThemeService(CommonService):
    """
    テーマ関連の処理を集約したサービスクラス
    """
    
    @staticmethod
    def normalize_axis_lines(lines: list[str]) -> list[str]:
        """
        モデルが返した対立軸の行を、立場ごとの一覧に整える

        行頭の「- 」と前後の空白、空の行を取り除く。モデルが 2 つの立場を
        「A vs B」「A／B」のように 1 行で返したときは、区切りで分ける。

        Args:
            lines (list[str]): モデルの出力を行ごとに分けたもの

        Returns:
            list[str]: 立場の一覧
        """
        axis_list = [text.lstrip('- ').strip() for text in lines]
        axis_list = [text for text in axis_list if text]
        if len(axis_list) == 1:
            parts = [part.strip() for part in re.split(r"\s+vs\.?\s+|\s*[／/]\s*", axis_list[0], flags=re.IGNORECASE)]
            parts = [part for part in parts if part]
            if len(parts) >= 2:
                axis_list = parts
        return axis_list

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
        
        result["axis_list"] = self.normalize_axis_lines(result["axis_list"])
        
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
    
    
    def get_axis_chain(self) -> RunnableSerializable:
        """
        対立軸生成用のLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model=configs.constants.OPENAI_MODEL_LIGHT, reasoning_effort="low", verbosity="low"), StrOutputParser()
        return  self.get_prompt_callable("get_axis_standalone") | llm | parser | RunnableLambda(lambda x: x.splitlines())
    
    def get_comments_per_axis_chain(self) -> RunnableSerializable:
        """
        対立軸ごとのコメント内容を取得するLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model=configs.constants.OPENAI_MODEL_LIGHT, reasoning_effort="low", verbosity="low"), StrOutputParser()
        comments_prompt = self.get_prompt_callable("get_comments_standalone")
        
        # 空白行はフィルターでカットして返却
        return (
            comments_prompt | llm | parser | RunnableLambda(lambda s: [item.strip() for item in s.splitlines() if item and item.strip()])
        )


    def get_description_chain(self) -> RunnableSerializable:
        """
        テーマの説明を取得するLCELチェインを取得

        Returns:
            _type_: LCELチェイン
        """
        llm, parser = ChatOpenAI(model=configs.constants.OPENAI_MODEL_LIGHT, reasoning_effort="low", verbosity="low"), StrOutputParser()
        return (
            self.get_prompt_callable("get_description_standalone")
            | llm
            | parser
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