# バッチLambda化編 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** バッチ処理（投票情報更新・テーマ作成）のビジネスロジックをルーターからサービス層へ抽出し、EventBridge Schedulerから直接起動できるLambdaハンドラを追加する。batch-createは「1起動1件処理」に対応する。

**Architecture:** ルーター（HTTP + アクセスキー認証、現行cron用に温存）とLambdaハンドラ（IAM認証、EventBridge用）が同一のサービスメソッド `BatchService.update_themes()` / `publish_approved_drafts(limit)` を呼ぶ二重入口構成。Lambdaハンドラは CommonRoute を経由しないため、S3クライアント・DraftStoreを自前で初期化する。コンテナイメージ化（Dockerfile.lambda・Chromium同梱）は**Terraform編に委譲**し、本プランはコードとテストのみ。

**Tech Stack:** Python 3.11 / pytest + unittest.mock / moto（既存導入済み）

**前提・注意:**
- ブランチ: `feature/serverless-migration` の続き。コミットは触ったファイルのみ明示 `git add`。
- テスト実行: `cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web`（依存追加なし・イメージ再ビルド不要）。
- ルーター側のHTTPエンドポイント（/batch/update, /batch/create_all）は**現行cronが使うため挙動を変えない**（アクセスキー検証→サービス呼び出し→同一レスポンス）。

---

## File Structure

```
Server/web/
├── api/
│   ├── services/batch.py          # 変更: THEME_HEADERS/CSV_CACHE_CONTROL移設、update_themes/publish_approved_drafts追加
│   ├── routers/batch.py           # 変更: update/create_allをサービス呼び出しに薄型化
│   └── lambda_handlers/           # 新規: EventBridge直起動用エントリポイント
│       ├── __init__.py
│       ├── batch_update.py
│       └── batch_create.py
└── tests/
    ├── test_batch_service.py      # 新規
    └── test_lambda_handlers.py    # 新規
```

---

### Task 1: `update_themes()` のサービス層抽出

**Files:**
- Modify: `Server/web/api/services/batch.py`
- Modify: `Server/web/api/routers/batch.py`
- Test: `Server/web/tests/test_batch_service.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_batch_service.py`:

```python
from unittest.mock import AsyncMock, patch

from api.services.batch import BatchService, CSV_CACHE_CONTROL

THEMES = [
    {"id": "1", "category": "1", "title": "T1", "description": "d", "conversation_id": "c1",
     "report_id": "r1", "votes": "10", "comments": "2", "create_date": "2026-01-01 00:00:00"},
    {"id": "2", "category": "2", "title": "T2", "description": "d", "conversation_id": "c2",
     "report_id": "r2", "votes": "5", "comments": "1", "create_date": "2026-01-01 00:00:00"},
]


def _report(votes_list):
    # comment-groups.csv相当: 1行=1コメント
    return [{"comment-id": str(i), "total-votes": str(v)} for i, v in enumerate(votes_list)]


async def test_update_themes_uploads_only_changed():
    service = BatchService()
    service.s3 = AsyncMock()

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([6, 6])),   # c1: 合計12票 ≠ 10 → 更新対象
             ("csv2", _report([5])),      # c2: 合計5票 = 5 → 変化なし
         ])):
        updated = await service.update_themes()

    assert updated == 1
    # report_c1 と themes.csv の2回のみアップロード
    keys = [call.args[0] for call in service.s3.upload_bytes.await_args_list]
    assert keys == ["csv/report/report_c1.csv", "csv/themes.csv"]
    # Cache-Controlが必ず付与される
    for call in service.s3.upload_bytes.await_args_list:
        assert call.kwargs["cache_control"] == CSV_CACHE_CONTROL
    # themes.csv には更新後の票数が反映されている
    themes_body = service.s3.upload_bytes.await_args_list[1].args[1].decode("utf-8")
    assert "12" in themes_body


async def test_update_themes_no_change_no_upload():
    service = BatchService()
    service.s3 = AsyncMock()

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([10])),
             ("csv2", _report([5])),
         ])):
        updated = await service.update_themes()

    assert updated == 0
    service.s3.upload_bytes.assert_not_awaited()
```

- [ ] **Step 2: 失敗確認**

Expected: `ImportError: cannot import name 'CSV_CACHE_CONTROL' from 'api.services.batch'`

- [ ] **Step 3: サービスに定数とメソッドを実装**

`api/services/batch.py` — import群の直後（`class BatchService` の前）に追加:

```python
THEME_HEADERS = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date"]
"""テーマ記録用CSVのカラム一覧"""

CSV_CACHE_CONTROL = "max-age=300"
"""CSV配信のCloudFront TTL。無効化APIの代わりにオブジェクト側のヘッダで鮮度を制御する"""
```

`BatchService` クラス内（`get_report_csv` の後）にメソッド追加:

```python
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

        # 取得内容をテーマ一覧CSVに反映
        result_themes = utils.Common.merge_lists(themes_list, update_themes)
        fixed_theme_csv_text = utils.CSV.to_csv(result_themes, THEME_HEADERS)

        Logger.debug("S3に更新を実施")

        # 変更があった集計CSVをS3に格納
        for conversation_id, report_csv_str in update_comment_csv.items():
            await self.s3.upload_bytes(f"csv/report/report_{conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

        # テーマ一覧CSVを更新
        await self.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

        return len(update_themes)
```

- [ ] **Step 4: ルーターを薄型化**

`api/routers/batch.py`:
- 冒頭の `THEME_HEADERS` / `CSV_CACHE_CONTROL` 定義を削除し、importを `from api.services.batch import BatchService, THEME_HEADERS, CSV_CACHE_CONTROL` に変更（delete エンドポイントが引き続き両定数を使用）。
- `update` の本体（`themes_str, themes_list = await service.get_theme_csv()` から try/except ブロックまで）を次の1行に置き換え:

```python
    # 全テーマの投票情報を更新
    await service.update_themes()
```

- [ ] **Step 5: テストPASS + 回帰確認 + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
git add Server/web/api/services/batch.py Server/web/api/routers/batch.py Server/web/tests/test_batch_service.py
git commit -m "refactor: 投票情報更新ロジックをBatchService.update_themesに抽出"
```

---

### Task 2: `publish_approved_drafts(limit)` のサービス層抽出

**Files:**
- Modify: `Server/web/api/services/batch.py`（`import api.models.types as types` を追加）
- Modify: `Server/web/api/routers/batch.py`
- Test: `Server/web/tests/test_batch_service.py`（追記）

- [ ] **Step 1: 失敗するテストを追記**

```python
from api.repositories.draft import Draft


def _draft(id_, name):
    return Draft(id=id_, theme_name=name, theme_description="説明",
                 theme_comments="A###br###B", theme_category=1, post_status=2)


def _service_with_mocks(drafts, theme_infos):
    service = BatchService()
    service.s3 = AsyncMock()
    service.draft_store = AsyncMock()
    service.draft_store.select_by_post_status = AsyncMock(return_value=drafts)
    return service, theme_infos


async def test_publish_approved_drafts_limit_1():
    drafts = [_draft(1, "先"), _draft(2, "後")]
    service, _ = _service_with_mocks(drafts, None)

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [{"id": "9"}]))), \
         patch.object(BatchService, "create_theme", AsyncMock(return_value=(
             "report-csv", {"id": "10", "conversation_id": "c10", "report_id": "r10"}))) as create_mock:
        processed = await service.publish_approved_drafts(limit=1)

    assert processed == 1
    create_mock.assert_awaited_once()                      # 1件しか作らない
    service.draft_store.update_post_info.assert_awaited_once()
    args = service.draft_store.update_post_info.await_args.args
    assert args[0].id == 1                                 # 先頭(最古)の下書きが対象
    assert args[1:] == ("c10", "r10", 3)                   # POSTED=3
    service.draft_store.commit.assert_awaited_once()

    # themes.csv 1回 + report 1回
    keys = [call.args[0] for call in service.s3.upload_bytes.await_args_list]
    assert keys == ["csv/themes.csv", "csv/report/report_c10.csv"]


async def test_publish_approved_drafts_empty_returns_zero():
    service, _ = _service_with_mocks([], None)
    with patch.object(BatchService, "get_theme_csv", AsyncMock()) as get_csv_mock:
        processed = await service.publish_approved_drafts()
    assert processed == 0
    get_csv_mock.assert_not_awaited()      # 対象ゼロならS3にも触らない
    service.s3.upload_bytes.assert_not_awaited()


async def test_publish_approved_drafts_rolls_back_on_store_error():
    drafts = [_draft(1, "X")]
    service, _ = _service_with_mocks(drafts, None)
    service.draft_store.update_post_info = AsyncMock(side_effect=RuntimeError("boom"))

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", []))), \
         patch.object(BatchService, "create_theme", AsyncMock(return_value=("csv", {"id": "1", "conversation_id": "c", "report_id": "r"}))):
        try:
            await service.publish_approved_drafts()
            assert False, "should raise"
        except RuntimeError:
            pass

    service.draft_store.rollback.assert_awaited_once()
```

- [ ] **Step 2: 失敗確認**

Expected: `AttributeError: ... has no attribute 'publish_approved_drafts'`

- [ ] **Step 3: 実装**

`api/services/batch.py` — importに `import api.models.types as types` を追加し、`update_themes` の後にメソッド追加:

```python
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
        for t_draft in t_draft_list:
            # コメントリストを文字列にパース
            comments = t_draft.theme_comments.split(configs.constants.SPLITTER)

            # テーマを作成
            report_csv_str, theme_info = await self.create_theme(theme_list, str(t_draft.theme_name), str(t_draft.theme_description), comments, str(t_draft.theme_category))

            # テーマ一覧に追加
            theme_list.append(theme_info)
            report_csv_list.append(report_csv_str)

            t_draft.conversation_id = theme_info["conversation_id"]
            t_draft.report_id = theme_info["report_id"]

        # テーマ一覧CSVをS3にアップ
        fixed_theme_csv_text = utils.CSV.to_csv(theme_list, THEME_HEADERS)
        await self.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

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
```

- [ ] **Step 4: ルーターを薄型化**

`api/routers/batch.py` の `create_all` 本体（`t_draft_list = ...` から try/except commit ブロックまで）を次に置き換え:

```python
    # 承認済テーマを一括作成（HTTP経由は現行cron互換のため全件処理）
    await service.publish_approved_drafts()
```

- [ ] **Step 5: テストPASS + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
git add Server/web/api/services/batch.py Server/web/api/routers/batch.py Server/web/tests/test_batch_service.py
git commit -m "refactor: テーマ作成ロジックをpublish_approved_draftsに抽出しlimit対応"
```

---

### Task 3: Lambdaハンドラの追加

**Files:**
- Create: `Server/web/api/lambda_handlers/__init__.py`（空）
- Create: `Server/web/api/lambda_handlers/batch_update.py`
- Create: `Server/web/api/lambda_handlers/batch_create.py`
- Test: `Server/web/tests/test_lambda_handlers.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_lambda_handlers.py`:

```python
from unittest.mock import AsyncMock, patch

from api.services.batch import BatchService


def test_batch_update_handler_returns_result():
    from api.lambda_handlers import batch_update

    with patch.object(BatchService, "initialize_utils", AsyncMock()), \
         patch.object(BatchService, "update_themes", AsyncMock(return_value=3)), \
         patch("api.lambda_handlers.batch_update.create_draft_store", return_value=AsyncMock()):
        result = batch_update.handler({}, None)

    assert result == {"is_success": True, "updated": 3}


def test_batch_create_handler_processes_one():
    from api.lambda_handlers import batch_create

    with patch.object(BatchService, "initialize_utils", AsyncMock()), \
         patch.object(BatchService, "publish_approved_drafts", AsyncMock(return_value=1)) as publish_mock, \
         patch("api.lambda_handlers.batch_create.create_draft_store", return_value=AsyncMock()):
        result = batch_create.handler({}, None)

    assert result == {"is_success": True, "processed": 1}
    publish_mock.assert_awaited_once_with(limit=1)


def test_handler_closes_s3_even_on_error():
    from api.lambda_handlers import batch_update

    s3_mock = AsyncMock()

    async def _init(self):
        self.s3 = s3_mock

    with patch.object(BatchService, "initialize_utils", _init), \
         patch.object(BatchService, "update_themes", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("api.lambda_handlers.batch_update.create_draft_store", return_value=AsyncMock()):
        try:
            batch_update.handler({}, None)
            assert False, "should raise"
        except RuntimeError:
            pass

    s3_mock.close.assert_awaited_once()
```

- [ ] **Step 2: 失敗確認**

Expected: `ModuleNotFoundError: No module named 'api.lambda_handlers'`

- [ ] **Step 3: 実装**

`api/lambda_handlers/__init__.py` — 空ファイル。

`api/lambda_handlers/batch_update.py`:

```python
"""
投票情報自動更新バッチのLambdaエントリポイント。

EventBridge Scheduler から5分間隔で直接起動される。
起動経路がIAMで保護されるため、HTTP経由(routers/batch.py)と異なりアクセスキー検証は行わない。
APP_ENV=serverless 前提（DraftStoreはDynamoDB、RDB接続なし）。
"""
import asyncio

from api.logger import Logger
from api.repositories import create_draft_store
from api.services.batch import BatchService


async def _run() -> dict:
    service = BatchService()
    await service.initialize_utils()
    service.db_session = None
    service.draft_store = create_draft_store(None)
    try:
        updated = await service.update_themes()
        return {"is_success": True, "updated": updated}
    finally:
        s3 = getattr(service, "s3", None)
        if s3 is not None:
            await s3.close()


def handler(event, context):
    result = asyncio.run(_run())
    Logger.info(f"batch_update result: {result}")
    return result
```

`api/lambda_handlers/batch_create.py`:

```python
"""
テーマ作成バッチのLambdaエントリポイント。

EventBridge Scheduler から15分間隔で直接起動され、承認済み下書きを1件だけ処理する
（Lambdaの15分制限内に確実に収め、失敗時の影響を1件に限定するため。残件は次回起動で処理）。
起動経路がIAMで保護されるため、アクセスキー検証は行わない。
APP_ENV=serverless 前提（DraftStoreはDynamoDB、RDB接続なし）。
"""
import asyncio

from api.logger import Logger
from api.repositories import create_draft_store
from api.services.batch import BatchService


async def _run() -> dict:
    service = BatchService()
    await service.initialize_utils()
    service.db_session = None
    service.draft_store = create_draft_store(None)
    try:
        processed = await service.publish_approved_drafts(limit=1)
        return {"is_success": True, "processed": processed}
    finally:
        s3 = getattr(service, "s3", None)
        if s3 is not None:
            await s3.close()


def handler(event, context):
    result = asyncio.run(_run())
    Logger.info(f"batch_create result: {result}")
    return result
```

- [ ] **Step 4: 全テストPASS + Docker回帰（MySQL経路） + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
# ポートずらしオーバーライドで healthcheck 疎通（cron互換のHTTPバッチ経路が生きていること）
git add Server/web/api/lambda_handlers Server/web/tests/test_lambda_handlers.py
git commit -m "feat: バッチのLambdaエントリポイントを追加（batch-createは1起動1件処理）"
```

---

## 後続プラン（本プランのスコープ外）

- **Terraform編**: Lambdaコンテナイメージ（api用 / batch-create用のChromium同梱イメージ）のDockerfileとローカルRIE検証、ECR、DynamoDBテーブル、API GW、EventBridge Scheduler、SSM、監視の実リソース構築

## Self-Review 結果

- 設計書§2.1との対応: batch-update=EventBridge直起動✅ batch-create=1起動1件✅ アクセスキー不要化✅
- HTTP経路（現行cron）の互換: update/create_allのレスポンス・認証・全件処理の挙動を維持✅
- 型整合: `publish_approved_drafts` は Task 2 定義と Task 3 呼び出し（`limit=1`）で一致。`update_post_info(draft, conversation_id, report_id, post_status)` は DraftStore インターフェース（DynamoDB移行編Task 1）と一致✅
- update_themes抽出で `total_comments` の数え方を `len(comments)` に簡素化（挙動同一）✅
