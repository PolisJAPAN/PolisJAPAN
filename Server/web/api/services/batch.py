import json
import os
from functools import partial
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import (RunnableLambda, RunnableParallel, RunnableSerializable, RunnableBranch)
from langchain_openai import ChatOpenAI
from langsmith import Client as LangSmithClient
from pydantic import BaseModel, Field
from selenium.webdriver.common.by import By

import api.configs as configs
import api.cruds as cruds
from api import utils
from api.core.common_service import CommonService
from api.logger import Logger
from api.utils.storage_s3 import StorageS3Error, StorageS3PreconditionError
from api.utils.web_loader_chrome import WebLoaderChrome
import api.models.types as types

THEME_HEADERS = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date"]
"""テーマ記録用CSVのカラム一覧"""

CSV_CACHE_CONTROL = "max-age=300"
"""CSV配信のCloudFront TTL。無効化APIの代わりにオブジェクト側のヘッダで鮮度を制御する"""


class BatchService(CommonService):
    """
    バッチ関連の処理を集約したサービスクラス
    """
    
    # ###########################################################################
    # CSV取得関連
    # ###########################################################################
    
    async def get_theme_csv(self) -> tuple[str, list]:
        """
        テーマCSVをS3から取得

        Returns:
            tuple[str, list]: CSV文字列, パース済CSVデータ
        """
        # 管理しているテーマ一覧のCSVをS3から取得する
        themes_bytes = await self.s3.get_bytes("csv/themes.csv")
        
        # テーマ一覧CSVをリストにパース
        themes_str = themes_bytes.decode("utf-8")
        themes_list = utils.CSV.parse_csv(themes_str)
        
        # データをid別で並べ替え
        sorted_themes_list = utils.Common.sort_list(themes_list, "id")
        
        return themes_str, sorted_themes_list
    
    async def get_report_csv(self, report_id: str) -> tuple[str, list]:
        """
        レポートIDを指定してPolisからCSVを取得

        Args:
            report_id (str): レポートID

        Returns:
            tuple[str, list]: CSV文字列, パース済CSVデータ
        """
        report_csv_str = await utils.WebLoaderHttpx.fetch_url(f"https://pol.is/api/v3/reportExport/{report_id}/comment-groups.csv")
        comments = utils.CSV.parse_csv(report_csv_str)

        return report_csv_str, comments

    THEMES_CSV_KEY = "csv/themes.csv"
    """テーマ一覧CSVのS3キー"""

    async def write_themes_csv(self, mutate, max_attempts: int = 3) -> list:
        """
        themes.csv を楽観ロック(ETag If-Match)つきで安全に更新する。

        batch-update(5分毎)とbatch-create(15分毎・実行数分)が同じファイルを
        read-modify-writeするため、素朴な上書きでは公開直後のテーマ行を
        取りこぼす競合がある。取得時のETagを条件に書き込み、競合を検出したら
        最新を再取得してmutateを適用し直す。

        Args:
            mutate (Callable[[list], list]): 最新のテーマ一覧を受け取り更新後の一覧を返す関数。
                競合リトライ時に再実行されるため、冪等であること。
            max_attempts (int): 最大試行回数。

        Returns:
            list: 書き込みに成功した更新後のテーマ一覧。
        """
        for attempt in range(max_attempts):
            data, etag = await self.s3.get_bytes_and_etag(self.THEMES_CSV_KEY)
            themes_list = utils.Common.sort_list(utils.CSV.parse_csv(data.decode("utf-8")), "id")

            new_list = mutate(themes_list)
            fixed_theme_csv_text = utils.CSV.to_csv(new_list, THEME_HEADERS)

            try:
                await self.s3.upload_bytes(self.THEMES_CSV_KEY, fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL, if_match=etag)
                return new_list
            except StorageS3PreconditionError:
                Logger.info(f"themes.csvの書き込み競合を検出。最新を再取得してリトライ ({attempt + 1}/{max_attempts})")

        raise StorageS3Error("themes.csv update failed: write conflict retries exhausted")

    # ###########################################################################
    # バッチ本体（ルーター/Lambdaハンドラ共通の入口）
    # ###########################################################################

    async def update_themes(self) -> int:
        """
        全テーマの投票数・コメント数をPolisから取得し、変化があればS3のCSVを更新する。

        Returns:
            int: 更新したテーマ数（0なら S3 への書き込みなし）
        """
        # 管理しているテーマ一覧のCSVをS3から取得する
        themes_str, themes_list = await self.get_theme_csv()

        # 更新するデータのみのリスト
        update_themes = []
        update_comment_csv = {}

        # 各テーマ用のデータを取得
        for theme in themes_list:

            # Polisから集計CSVを取得
            report_csv_str, comments = await self.get_report_csv(theme["report_id"])

            # コメント数、投票数を集計
            total_comments = len(comments)
            total_votes = sum(int(comment["total-votes"]) for comment in comments)

            Logger.debug(f"{theme['title']} before {theme['votes']} -> after {total_votes}  (Refresh -> {int(theme['votes']) != int(total_votes)})")

            # 現在S3に保存済みの集計CSVと比較
            if int(theme["votes"]) != int(total_votes):
                # 変更があった場合は、取得したファイルを設置用に配列に格納
                update_row = theme.copy()
                update_row["votes"] = str(total_votes)
                update_row["comments"] = str(total_comments)
                update_themes.append(update_row)

                # S3にアップするリストにCSVを追加
                update_comment_csv[theme["conversation_id"]] = report_csv_str

        if not update_comment_csv:
            return 0

        Logger.debug("S3に更新を実施")

        # 変更があった集計CSVをS3に格納
        for conversation_id, report_csv_str in update_comment_csv.items():
            await self.s3.upload_bytes(f"csv/report/report_{conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

        # テーマ一覧CSVを楽観ロックで更新
        # （並行するbatch-createが追記したテーマ行を上書きで消さないよう、最新版にマージし直す）
        await self.write_themes_csv(lambda current: utils.Common.merge_lists(current, update_themes))

        return len(update_themes)

    async def publish_approved_drafts(self, limit: Optional[int] = None) -> int:
        """
        承認済(APPROVED)の下書きをPolis上に作成し、CSVとデータストアへ反映する。

        Args:
            limit (Optional[int]): 処理する最大件数。Lambda(15分制限)からは1を指定し、
                残りは次回スケジュールに委ねる。Noneなら全件（現行cronと同じ挙動）。

        Returns:
            int: 処理した下書き件数
        """
        # 承認済テーマ一覧を取得
        t_draft_list = await self.draft_store.select_by_post_status(types.PostStatus.APPROVED.value)

        if limit is not None:
            t_draft_list = t_draft_list[:limit]

        if not t_draft_list:
            return 0

        Logger.debug(json.dumps([t_draft.theme_name for t_draft in t_draft_list], indent=4, ensure_ascii=False))

        # テーマ一覧を取得
        themes_str, theme_list = await self.get_theme_csv()

        # 承認済テーマを作成
        report_csv_list = []
        new_theme_infos = []
        for t_draft in t_draft_list:
            # コメントリストを文字列にパース
            comments = t_draft.theme_comments.split(configs.constants.SPLITTER)

            # テーマを作成
            report_csv_str, theme_info = await self.create_theme(theme_list, str(t_draft.theme_name), str(t_draft.theme_description), comments, str(t_draft.theme_category))

            # テーマ一覧に追加
            theme_list.append(theme_info)
            new_theme_infos.append(theme_info)
            report_csv_list.append(report_csv_str)

            t_draft.conversation_id = theme_info["conversation_id"]
            t_draft.report_id = theme_info["report_id"]

        # テーマ一覧CSVを楽観ロックで更新
        # （並行するbatch-updateの上書きに新テーマ行を消されないよう、最新版に追記し直す）
        await self.write_themes_csv(lambda current: current + new_theme_infos)

        # レポートから取得したファイルをS3にアップ（t_draftと対応づけ）
        for t_draft, report_csv_str in zip(t_draft_list, report_csv_list):
            await self.s3.upload_bytes(f"csv/report/report_{t_draft.conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

        # データストアへ反映
        try:
            for t_draft in t_draft_list:
                await self.draft_store.update_post_info(t_draft, t_draft.conversation_id, t_draft.report_id, types.PostStatus.POSTED.value)

            await self.draft_store.commit()
        except Exception as e:
            await self.draft_store.rollback()
            raise e

        return len(t_draft_list)

    # ###########################################################################
    # Polis登録関連
    # ###########################################################################
    
    async def create_theme(self, theme_list: list[dict], theme_name : str, theme_description : str, comments : list, category: str) -> tuple[str, dict]:
        """
        Polisへのテーマ登録処理

        Args:
            theme_list (list[dict]): 既存テーマ一覧
            theme_name (str): テーマ名
            theme_description (str): テーマ説明
            comments (list): コメント一覧
            category (str): カテゴリ

        Returns:
            tuple[str, list]: CSV文字列, 更新済テーマ情報
        """
        # Polis上でテーマを作成して必要情報を格納
        theme_info = self.create_theme_on_polis(theme_name, theme_description, comments, category)
        
        Logger.debug("作成されたテーマ情報を表示")
        Logger.debug(json.dumps(theme_info, indent=4, ensure_ascii=False))
        
        # レポートからファイルを取得
        report_csv_str, comments = await self.get_report_csv(theme_info["report_id"])
        
        # 末尾idを取得
        theme_info["id"] = self.get_themes_last_id(theme_list)
        
        # 作成日を取得
        theme_info["create_date"] = utils.Time.to_mysql_datetime_str(utils.Time.now())
        
        return report_csv_str, theme_info
    
    def create_theme_on_polis(self, theme_name : str, theme_description : str, comments : list, category: str) -> dict:
        """
        PolisWebページ上でのテーマ作成処理

        Args:
            theme_name (str): テーマ名
            theme_description (str): テーマ説明
            comments (list): コメント一覧
            category (str): カテゴリ

        Returns:
            dict: 作成後テーマ情報
        """

        result = {
            "id": None,
            "category": category,
            "title": theme_name,
            "description": theme_description,
            "conversation_id": "",
            "report_id": "",
            "votes": "0",
            "comments": len(comments),
            "create_date": "2025-09-12"
        }
        
        with utils.WebLoaderChrome() as web_loader_chrome:
            # Chromeドライバーの立ち上げ
            web_loader_chrome.get_driver("https://pol.is/signin")
            
            # 未ログイン状態の場合、ログインを実施
            # 認証情報は環境変数から取得（serverless環境ではTerraformがSSM経由で注入。
            # ローカルは Server/web/.env で設定）
            polis_user = os.environ.get("POLIS_LOGIN_USER", "")
            polis_password = os.environ.get("POLIS_LOGIN_PASSWORD", "")
            if not polis_user or not polis_password:
                raise RuntimeError("POLIS_LOGIN_USER / POLIS_LOGIN_PASSWORD が未設定です")
            if not web_loader_chrome.exists_wait(By.ID, "signoutLink", 10):
                web_loader_chrome.wait_for(By.ID, "signinButton", 30, True)
                web_loader_chrome.click(By.CSS_SELECTOR, "#signinButton")
                web_loader_chrome.wait_for(By.ID, "username", 15, True)
                web_loader_chrome.fill_input(By.ID, "username", polis_user)
                web_loader_chrome.fill_input(By.ID, "password", polis_password)
                web_loader_chrome.submit_form(By.XPATH, "/html/body/div/main/section/div/div/div/form")
                web_loader_chrome.wait_for(By.ID, "signoutLink", 15, True)
                Logger.debug("ログインに成功")
            
            # ログイン済みの場合
            # 新規テーマ作成画面に移動
            web_loader_chrome.click_button_contains_text("Create new conversation")
            Logger.debug("テーマ作成画面ボタンをクリック1")
            web_loader_chrome.click_button_contains_text("Create Conversation")
            Logger.debug("テーマ作成画面ボタンをクリック2")
            web_loader_chrome.wait_for(By.CSS_SELECTOR, '[data-testid^="top"]', 15, True)
            Logger.debug("テーマ作成画面を開く")
            
            # フォームに作成内容を挿入
            web_loader_chrome.fill_input(By.CSS_SELECTOR, '[data-testid^="top"]', theme_name)
            web_loader_chrome.fill_input(By.CSS_SELECTOR, '[data-testid^="description"]', theme_description)
            web_loader_chrome.click(By.XPATH, "/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div[5]/div[2]/button")
            Logger.debug("テーマと概要を記入")
            
            # # 各コメント内容を挿入
            for comment in comments:
                web_loader_chrome.fill_input(By.CSS_SELECTOR, '[data-testid^="seed_form"]', comment)
                web_loader_chrome.click(By.XPATH, "/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div[5]/div[2]/button")
                web_loader_chrome.wait_for_text(By.XPATH, "/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div[5]/div[2]/button", "Success!")
                Logger.debug(f"コメントを記入 {comment}")
            
            # グラフ表示を有効化
            web_loader_chrome.set_checkbox(By.CSS_SELECTOR, '[data-testid^="vis_type"]', True)
            
            # URLからidを取得
            url = web_loader_chrome._driver.current_url
            url_parsed = urlparse(url)
            conversation_id = url_parsed.path.rstrip("/").split("/")[-1]
            result["conversation_id"] = conversation_id
            Logger.debug(f"URLを取得 {conversation_id}")
            
            # レポートページ情報を取得
            # レポートページに遷移
            report_url = f"{url}/reports"
            web_loader_chrome.navigate(report_url)
            web_loader_chrome.wait_for(By.XPATH, '/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/button', 15, True)
            # レポート作成ボタンをクリック
            web_loader_chrome.click(By.XPATH, "/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div/div[1]/button")
            web_loader_chrome.wait_for(By.XPATH, '/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div/div[2]/div/div/span[2]', 15, True)
            # レポートリンクからIDを取得
            report_url = web_loader_chrome.get_text(By.XPATH, '/html/body/div/div/div[2]/div/div[2]/div/div[2]/div/div/div[2]/div/div/span[2]')
            report_id = report_url.replace("\n", "").replace("Report ID: ", "")
            result["report_id"] = report_id
            Logger.debug(result["report_id"])
            
            web_loader_chrome.save_screenshot("create")
            
        return result
    
    def get_themes_last_id(self, themes_list: list[dict]) -> str:
        """
        既存テーマ一覧から最新IDを取得

        Args:
            themes_list (list[dict]): 既存テーマ一覧

        Returns:
            str: 最新ID
        """
        last_id = themes_list[len(themes_list) - 1]["id"]
        return str(int(last_id) + 1)
    
    # ###########################################################################
    # テーマ生成関連処理
    # ###########################################################################
    
    async def get_info_from_twitter(self, html: str) -> tuple[str, dict, list, str]:
        """
        Twitterからのテーマ情報取得処理

        Args:
            html (str): 情報取得元になるhtml文字列

        Returns:
            tuple[str, dict, list, str]: ページタイトル、核となるツイート情報、反応ツイート情報、背景情報
        """
        
        with utils.WebLoaderChrome() as web_loader_chrome:
            # ページタイトルを取得
            page_title: str = ""
            Logger.debug("ページタイトル")
            Logger.debug(page_title)
            
            # ページ内ツイート情報を抽出
            tweet_schema = {
                "tweet_text": (utils.HTMLParser.parse_type.TEXT, '[data-testid="tweetText"]'),
                # "tweet_href": (utils.HTMLParser.parse_type.LINK, "> span.status span:nth-of-type(2) a.link"),
            }
            tweet_list = utils.HTMLParser.get_items_by_schema(html, '[data-testid="tweet"]', tweet_schema, base_url = "")
            Logger.debug("対象ツイートリスト")
            Logger.debug(json.dumps(tweet_list, indent=4, ensure_ascii=False))

            # メイン意見を取得
            main_tweet: dict = tweet_list[0]
            
            # 最新5件の反応を取得
            reaction_tweet_list: list[dict] = tweet_list[1:6]
            
            background_url_list = self.get_background_url_for_twitter("", html)
            Logger.debug("対象リンクリスト")
            Logger.debug(json.dumps(background_url_list, indent=4, ensure_ascii=False))
            background_detail: str = self.get_background_detail(background_url_list, web_loader_chrome)
            background_detail: str = ""
            
        return page_title, main_tweet, reaction_tweet_list, background_detail

    async def get_info_from_toggetter(self, url: str) -> tuple[str, dict, list, str]:
        """
        Togetterからのテーマ情報取得処理

        Args:
            url (str): 対象URL

        Returns:
            tuple[str, dict, list, str]: ページタイトル、核となるツイート情報、反応ツイート情報、背景情報
        """
        
        with utils.WebLoaderChrome() as web_loader_chrome:
            # Chromeドライバーの立ち上げ
            web_loader_chrome.get_driver(url)
            
            # toggeterから取得
            web_loader_chrome.wait_for(By.CSS_SELECTOR, '.entry_title')
            web_loader_chrome.save_screenshot("generate")
            
            html = web_loader_chrome.get_current_html()
            
            # ページタイトルを取得
            page_title_schema = {
                "page_title": (utils.HTMLParser.parse_type.TEXT, "a.info_title"),
            }
            page_title_data = utils.HTMLParser.get_single_item_by_schema(html, "h1.entry_title", page_title_schema, base_url = url)
            page_title: str = page_title_data["page_title"]
            Logger.debug(page_title)
            
            # ページ内ツイート情報を抽出
            tweet_schema = {
                "tweet_user": (utils.HTMLParser.parse_type.TEXT, "> span a span.status_name"),
                "tweet_text": (utils.HTMLParser.parse_type.TEXT, "> p.tweet"),
                "tweet_href": (utils.HTMLParser.parse_type.LINK, "> span.status span:nth-of-type(2) a.link"),
            }
            tweet_list = utils.HTMLParser.get_items_by_schema(html, ".type_tweet", tweet_schema, base_url = url)

            # メイン意見を取得
            main_tweet: dict = tweet_list[0]
            
            # 最新5件の反応を取得
            reaction_tweet_list: list[dict] = tweet_list[1:6]
            
            background_url_list = self.get_background_url_for_togetter(url, html)
            background_detail: str = self.get_background_detail(background_url_list, web_loader_chrome)
            
        return page_title, main_tweet, reaction_tweet_list, background_detail
    
    def get_background_url_for_twitter(self, url : str, html : str) -> list:
        """
        Twitter内のリンク情報の取得処理

        Args:
            url (str): 元URL
            html (str): 情報取得元のhtml

        Returns:
            list: リンク一覧
        """
        
        # 背景情報を取得
        link_schema = {
            "link_href": (utils.HTMLParser.parse_type.LINK, '[data-testid="card.layoutLarge.media"] [role="link"]'),
        }
        link_list = utils.HTMLParser.get_items_by_schema(html, '[data-testid="tweet"]', link_schema, base_url = url)
        new_link_list = [d for d in link_list if d["link_href"] != ""]
        
        return new_link_list
    
    def get_background_url_for_togetter(self, url : str, html : str) -> list:
        """
        Twitter内のリンク情報の取得処理 

        Args:
            url (str): 元URL
            html (str): 情報取得元のhtml

        Returns:
            list: リンク一覧
        """
        
        # 背景情報を取得
        link_schema = {
            "link_text": (utils.HTMLParser.parse_type.TEXT, "> span.title a"),
            "link_href": (utils.HTMLParser.parse_type.LINK, "> span.title a"),
        }
        link_list = utils.HTMLParser.get_items_by_schema(html, "div.type_url", link_schema, base_url = url)
        new_link_list = [d for d in link_list if d["link_href"] != ""]
        
        return new_link_list

    def get_background_detail(self, new_link_list : list, web_loader_chrome : WebLoaderChrome) -> str:
        """
        リンクから背景情報を抽出する処理

        Args:
            new_link_list (list): リンク一覧
            web_loader_chrome (WebLoaderChrome): 画面操作用のwebdriver

        Returns:
            str: 取得した背景情報テキスト
        """
        if len(new_link_list) == 0:
            return ""
        
        # リンクから、リンク先のWEBページ内容を取得する
        main_link = new_link_list[0]
        web_loader_chrome.navigate(main_link["link_href"])
        web_loader_chrome.wait_for(By.CSS_SELECTOR, 'body')
        web_loader_chrome.wait_seconds(10)
        main_link_html = web_loader_chrome.get_current_html()
        main_link_body = utils.HTMLParser.get_scope_html(html = main_link_html, scope_selector = "body", exclude_script = True)
        Logger.debug("リンク先HTML取得")
        Logger.debug(main_link_body)

        # 記事本体内容を取得するためのセレクタを取得
        selector = self.get_background_selector(main_link_body)
        
        # セレクタが特定できない場合、ボディをそのまま使用。精度は下がるので例外的措置
        if not selector:
            Logger.debug(f"セレクタが特定できなかったため、body全体を背景情報として使用します。 selector: {selector}")
            return main_link_body
    
        # 背景情報をページから抽出
        article_schema = {
            "text": (utils.HTMLParser.parse_type.GROUP, "*"),
        }
        article_list = utils.HTMLParser.get_items_by_schema(main_link_body, selector, article_schema, base_url = main_link["link_href"])
        Logger.debug("記事本文を取得")
        Logger.debug(json.dumps(article_list, indent=4, ensure_ascii=False))
        
        if len(article_list) == 0:
            return ""
        
        background_detail = article_list[0]["text"]
        return background_detail
    
    def get_background_selector(self, html : str) -> str:
        """
        背景情報収集用のセレクタを取得する処理

        Args:
            html (str): 対象のページHTML全部

        Returns:
            str: セレクタ
        """
        
        # 1) プロンプト（{topic}を埋め込む）
        prompt = self.get_prompt_callable("get_background_selector")
        
        # 2) モデル（GPT-5 を指定）
        llm = ChatOpenAI(model="gpt-5-nano")

        # 3) 出力パーサ（ChatMessage → str）
        parser = StrOutputParser()

        # 4) LCEL で直列合成
        chain = prompt | llm | parser

        # 5) 実行（単発）
        output = chain.invoke({"html" : html.replace("{", "").replace("}", "")})
        Logger.debug("背景ページセレクタ取得")
        Logger.debug(output)
        
        return output

    async def generate_theme(self, theme: Optional[str], page_title: str, main_tweet: dict, reaction_tweet_list: list[dict], background_detail: str) -> dict:
        """
        テーマ情報の生成を行う処理

        Args:
            page_title (str): ページタイトル
            main_tweet (dict): 核となるツイート情報
            reaction_tweet_list (list[dict]): 核ツイートへの反応一覧
            background_detail (str): 背景情報

        Returns:
            dict: テーマ投稿に必要な生成済データ一括
        """
        
        def build_reaction_text(inputs: dict) -> str:
            """反応のテキストを展開する処理"""
            return "\n".join([
                f"## 意見{i+1}\n    {item['tweet_text']}"
                for i, item in enumerate(inputs["reaction_tweet_list"])
            ])
        
        def _has_theme(input_dict: dict) -> bool:
            """入力に theme が既に設定されているかを判定する。"""
            theme_value = input_dict.get("theme")
            return isinstance(theme_value, str) and len(theme_value.strip()) > 0

        def _extract_existing_theme(input_dict: dict) -> str:
            """既に存在する theme をそのまま返す。"""
            return input_dict["theme"]

        def _always_true(input_dict: dict) -> bool:
            """常に True を返すプレディケート（フォールバック用）"""
            return True

        # 1. LCELのエントリーポイントになるデータ
        def get_state(args: dict) -> dict:
            return {
                "page_title": args["page_title"],
                "main_tweet_text": args["main_tweet"]["tweet_text"],
                "reaction_text": build_reaction_text(args),
                "detail": args["background_detail"],
            }
        state = RunnableLambda(get_state) #callableで書く必要があるのでメソッドで定義

        # 2. LCEL で直列化 処理は各チェイン内を参照
        full_chain = (state
            .assign(theme=RunnableBranch(
                (_has_theme, _extract_existing_theme),
                (_always_true, self.get_theme_chain()),
            ))
            .assign(axis_list=self.get_axis_chain())
            .assign(axises_and_comments=self.get_comments_by_axis_chain())
            .assign(description=self.get_description_chain())
            .assign(category=self.get_category_chain())
        )

        # 3. Chain実行
        result = await full_chain.ainvoke({
            "page_title": page_title,
            "main_tweet": main_tweet,
            "reaction_tweet_list": reaction_tweet_list,
            "background_detail": background_detail,
            "theme": theme,
        })
        
        # DB保存用にコメントだけ整形
        comments = []
        for comment_list in result["axises_and_comments"].values():
            comments += comment_list
            
        comment_str = "#####".join(comments)
        result["comments_str"] = comment_str
        
        return result
    
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
        llm, parser = ChatOpenAI(model="gpt-5"), StrOutputParser()
        return  self.get_prompt_callable("get_axis") | llm | parser | RunnableLambda(lambda x: x.splitlines())
    
    def get_comments_per_axis_chain(self) -> RunnableSerializable:
        """
        対立軸ごとのコメント内容を取得するLCELチェインを取得

        Returns:
            RunnableSerializable: LCELチェイン
        """
        llm, parser = ChatOpenAI(model="gpt-5-nano"), StrOutputParser()
        comments_prompt = self.get_prompt_callable("get_comments")
        
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
        llm, parser = ChatOpenAI(model="gpt-5-nano"), StrOutputParser()

        # コメント辞書をプロンプト用の1本の文字列へ整形
        def build_comments_text(x: Dict[str, Any]) -> Dict[str, Any]:
            axises_and_comments: Dict[str, List[str]] = x["axises_and_comments"]
            # 例のフォーマット：軸見出し行 + その配下にコメント行
            lines: List[str] = []
            for axis, comments in axises_and_comments.items():
                if not comments:
                    continue
                body = "\n        ".join(c for c in comments if c.strip())
                lines.append(f"    ## {axis}\n        {body}")
            x["comments_text"] = "\n".join(lines)
            return x

        return (
            RunnableLambda(build_comments_text)  # comments_text を作る
            | self.get_prompt_callable("get_description")
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