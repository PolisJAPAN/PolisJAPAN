import json
import os
from typing import Optional
from urllib.parse import urlparse

from selenium.webdriver.common.by import By

import api.configs as configs
from api import utils
from api.core.common_service import CommonService
from api.logger import Logger
from api.utils.storage_s3 import StorageS3Error, StorageS3PreconditionError
import api.models.types as types

THEME_HEADERS = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date", "created_at", "commented_at", "updated_at"]
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

            prev_votes = int(theme["votes"])
            prev_comments = int(theme["comments"])
            votes_changed = prev_votes != total_votes
            comments_changed = prev_comments != total_comments

            Logger.debug(f"{theme['title']} votes {prev_votes} -> {total_votes} / comments {prev_comments} -> {total_comments} (Refresh -> {votes_changed or comments_changed})")

            # 現在S3に保存済みの集計CSVと比較（投票または意見の変化で更新）
            if votes_changed or comments_changed:
                now_str = utils.Time.to_minute_datetime_str(utils.Time.now())

                # 変更があった場合は、取得したファイルを設置用に配列に格納
                update_row = theme.copy()
                update_row["votes"] = str(total_votes)
                update_row["comments"] = str(total_comments)
                # 投票または意見が増えた日時
                update_row["updated_at"] = now_str
                # 新しい意見（コメント）が投稿された日時（増加時のみ）
                if total_comments > prev_comments:
                    update_row["commented_at"] = now_str
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
            # 失敗時はリトライ回数を記録し、上限到達でFAILEDに隔離してから再送出する
            # （1件の失敗し続ける下書きが後続の承認済下書きを永久に塞がないため）
            # 対象はcreate_theme（下書き内容起因の失敗が起こりうる箇所）のみ。
            # 以降のCSV/S3/ストア更新の失敗はインフラ起因のため下書きには数えない
            try:
                report_csv_str, theme_info = await self.create_theme(theme_list, str(t_draft.theme_name), str(t_draft.theme_description), comments, str(t_draft.theme_category))
            except Exception:
                await self._record_publish_failure(t_draft)
                raise

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

    async def _record_publish_failure(self, t_draft) -> None:
        """
        Polis投稿失敗の記録処理。リトライ回数を加算し、上限到達でFAILEDに隔離する。

        呼び出し元が元の例外を再送出する前提のため、ここでの記録失敗は
        ログに残すのみで例外は伝播させない（元の失敗原因を隠さない）。
        """
        draft_id = t_draft.id
        try:
            # 先行下書きの未確定変更(conversation_id等)を後段のcommitで巻き込んで
            # 永続化しないよう、記録の前にセッションを巻き戻す（dynamodbではno-op）
            await self.draft_store.rollback()
            t_draft = await self.draft_store.increment_publish_retry(t_draft)
            if t_draft.publish_retry_count >= configs.constants.PUBLISH_RETRY_LIMIT:
                await self.draft_store.update_post_status(t_draft, types.PostStatus.FAILED.value)
                Logger.error(f"下書き(id={t_draft.id})が{t_draft.publish_retry_count}回連続で投稿失敗したため隔離しました(FAILED)。管理画面から再承認で再投稿できます")
            await self.draft_store.commit()
        except Exception as record_error:
            Logger.error(f"投稿失敗の記録に失敗: id={draft_id}, reason={record_error}")

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

        # 作成・更新日時（themes.csvの新列。分単位・JST）。新規テーマはどのソートでも先頭に来るよう3列とも作成時刻で初期化する
        now_minute_str = utils.Time.to_minute_datetime_str(utils.Time.now())
        theme_info["created_at"] = now_minute_str
        theme_info["commented_at"] = now_minute_str
        theme_info["updated_at"] = now_minute_str

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
