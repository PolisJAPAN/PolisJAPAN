# DynamoDB移行編 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `t_draft`（テーマ下書き）のデータアクセスを抽象化し、MySQL実装（現行）とDynamoDB実装（serverless用）を切り替え可能にする。あわせてMySQL→DynamoDBのデータ移行スクリプトを用意する。

**Architecture:** `DraftStore` インターフェースを新設し、ルーターは `service.draft_store` 経由でのみ下書きにアクセスする。バックエンドは `configs.constants.DATA_BACKEND`（`mysql` | `dynamodb`）で選択され、既存3環境はmysql、serverless環境はdynamodbになる。`common_route` は mysql バックエンドのときだけDBセッションを開く。DynamoDB実装は同期boto3を `asyncio.to_thread` でラップし、テストは moto でオフライン実行する。

**Tech Stack:** boto3（同期・moto互換）/ moto[dynamodb] / pytest / DynamoDBテーブル `polisjapan-drafts`（PK: `id`(N)、GSI: `post_status-index`）

**前提・注意:**
- ブランチ: 既存の `feature/serverless-migration` の続き。コミット対象は触ったファイルのみ明示 `git add`。
- テスト実行は基盤編と同じ: `cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web`（依存追加時はロック再生成→`docker compose build web`。ロック再生成は `docker run --rm -v $PWD/web:/app -w /app python:3.11-slim sh -c "pip install -q poetry && poetry lock"`）。
- Docker回帰はポート競合回避のためscratchpadの `compose-test-ports.yml` オーバーライドを使用（nginx:8090）。
- **ID設計**: 既存スキーマが `t_draft_id: int` のため、DynamoDBでも id は数値(N)を維持する。新規採番は `int(time.time())`（epoch秒）+ 条件付きPUT（`attribute_not_exists(id)`）衝突時+1リトライ。移行データは既存のAUTO_INCREMENT値（小さい整数）をそのまま使うため衝突しない。
- **既知の別問題（本プランでは触らない）**: `schemas/batch.py:175` の `t_draft_id: int = Field(ge=1, le=256)` はMySQLでもid>256の下書きを削除できない潜在バグ。別途相談。

---

## File Structure

```
Server/web/
├── pyproject.toml                        # 変更: moto追加(dev)
├── api/
│   ├── repositories/                     # 新規: DraftStore抽象化層
│   │   ├── __init__.py
│   │   ├── draft.py                      # Draftデータクラス + 共通インターフェース + factory
│   │   ├── draft_store_mysql.py          # cruds.TDraft への薄いラッパー
│   │   └── draft_store_dynamo.py         # boto3実装
│   ├── configs/constants.py              # 変更: DATA_BACKEND = "mysql" (基底デフォルト)
│   ├── configs/serverless/constants.py   # 変更: DATA_BACKEND = "dynamodb"
│   ├── core/common_service.py            # 変更: draft_store 属性追加
│   ├── core/common_route.py              # 変更: バックエンド別のセッション制御 + store生成
│   └── routers/{batch,admin,theme}.py    # 変更: cruds.TDraft → service.draft_store
├── scripts/
│   └── migrate_drafts_to_dynamodb.py     # 新規: 移行スクリプト（JSONエクスポート→DynamoDB投入+検証）
└── tests/
    ├── test_draft_store_dynamo.py        # 新規: moto でのDynamoDB実装テスト
    ├── test_draft_store_factory.py       # 新規: バックエンド選択とMySQLラッパー委譲
    └── test_migrate_script.py            # 新規: 移行スクリプトのテスト
```

---

### Task 1: Draftデータクラス + DynamoDraftStore（作成・取得系）

**Files:**
- Modify: `Server/web/pyproject.toml`（dev群に `moto (>=5.0,<6.0)` を追加 → ロック再生成 → `docker compose build web`）
- Create: `Server/web/api/repositories/__init__.py`
- Create: `Server/web/api/repositories/draft.py`
- Create: `Server/web/api/repositories/draft_store_dynamo.py`
- Test: `Server/web/tests/test_draft_store_dynamo.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_draft_store_dynamo.py`:

```python
import boto3
import pytest
from moto import mock_aws

from api.repositories.draft import Draft
from api.repositories.draft_store_dynamo import DynamoDraftStore

TABLE = "polisjapan-drafts-test"


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-3")
        client.create_table(
            TableName=TABLE,
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "N"},
                {"AttributeName": "post_status", "AttributeType": "N"},
            ],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "post_status-index",
                "KeySchema": [{"AttributeName": "post_status", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoDraftStore(table_name=TABLE)


async def test_insert_and_select_by_id(store):
    draft = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="テーマA", theme_description="説明A",
        theme_comments="c1###br###c2", theme_category=1, post_status=2,
    )
    assert isinstance(draft, Draft)
    assert draft.id >= 1
    assert draft.status == 1  # 有効フラグ自動付与
    assert draft.conversation_id == ""

    loaded = await store.select_by_id(draft.id)
    assert loaded is not None
    assert loaded.theme_name == "テーマA"
    assert loaded.post_status == 2
    assert loaded.create_date is not None  # datetimeとして復元される


async def test_select_by_id_not_found_returns_none(store):
    assert await store.select_by_id(999999999) is None


async def test_insert_id_collision_retries(store, monkeypatch):
    # 採番の起点を固定して2連続insert → 2件目は+1リトライで別IDになる
    monkeypatch.setattr("api.repositories.draft_store_dynamo.time.time", lambda: 1751000000.0)
    d1 = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="A", theme_description="", theme_comments="", theme_category=1, post_status=2,
    )
    d2 = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="B", theme_description="", theme_comments="", theme_category=1, post_status=2,
    )
    assert d1.id == 1751000000
    assert d2.id == 1751000001


async def test_select_all_returns_only_active_sorted(store):
    d1 = await store.insert_draft(title="", origin_url="", origin_html="",
                                  theme_name="A", theme_description="", theme_comments="", theme_category=1, post_status=2)
    d2 = await store.insert_draft(title="", origin_url="", origin_html="",
                                  theme_name="B", theme_description="", theme_comments="", theme_category=2, post_status=3)
    await store.delete_by_id(d2.id)  # 論理削除 → select_allから消える

    drafts = await store.select_all()
    assert [d.id for d in drafts] == [d1.id]
```

**注**: `delete_by_id` はTask 2実装だが、インターフェース定義はTask 1で置くため、このテストファイルは最初から全量を書く。Task 1の時点では `test_select_all_returns_only_active_sorted` は `delete_by_id` 未実装（NotImplementedError）で失敗してよい。Task 1完了条件は上3つのPASS。

- [ ] **Step 2: motoを追加してテストの失敗を確認**

`pyproject.toml` の dev 群に `"moto (>=5.0,<6.0)"` を追加し、ロック再生成 → `docker compose build web` → テスト実行。

Expected: `ModuleNotFoundError: No module named 'api.repositories'`

- [ ] **Step 3: 実装**

`Server/web/api/repositories/__init__.py`:

```python
from api.repositories.draft import Draft, DraftStore, create_draft_store
```

`Server/web/api/repositories/draft.py`:

```python
"""
テーマ下書き(t_draft相当)のデータアクセス抽象化層。

ルーターはこのモジュールの DraftStore インターフェースにのみ依存し、
実体は configs.constants.DATA_BACKEND で mysql / dynamodb を切り替える。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol

import api.configs as configs


@dataclass
class Draft:
    """バックエンド非依存の下書きレコード。tables.TDraftModel と同じ属性名を持つ
    (Pydanticの from_attributes バリデーションを通すため)。"""
    id: int
    title: str = ""
    origin_url: str = ""
    origin_html: str = ""
    theme_name: str = ""
    theme_description: str = ""
    theme_comments: str = ""
    theme_category: int = 0
    conversation_id: str = ""
    report_id: str = ""
    post_status: int = 0
    status: int = 1
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None


class DraftStore(Protocol):
    """下書きストアの共通インターフェース。実装は draft_store_mysql / draft_store_dynamo。"""

    async def insert_draft(self, *, title: str, origin_url: str, origin_html: str,
                           theme_name: str, theme_description: str, theme_comments: str,
                           theme_category: int, post_status: int) -> Draft: ...
    async def select_by_id(self, draft_id: int) -> Optional[Draft]: ...
    async def select_all(self) -> list[Draft]: ...
    async def select_by_post_status(self, post_status: int) -> list[Draft]: ...
    async def update_post_status(self, draft: Draft, post_status: int) -> Draft: ...
    async def update_content(self, draft: Draft, theme_name: Optional[str], theme_description: Optional[str],
                             theme_comments: Optional[str], theme_category: Optional[int]) -> Draft: ...
    async def update_post_info(self, draft: Draft, conversation_id: str, report_id: str, post_status: int) -> Draft: ...
    async def delete_by_id(self, draft_id: int) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


def create_draft_store(db_session=None) -> DraftStore:
    """DATA_BACKEND設定に応じたDraftStore実装を返す。

    Args:
        db_session: mysqlバックエンドの場合に必須の非同期DBセッション。
    """
    backend = getattr(configs.constants, "DATA_BACKEND", "mysql")
    if backend == "dynamodb":
        from api.repositories.draft_store_dynamo import DynamoDraftStore
        return DynamoDraftStore()
    from api.repositories.draft_store_mysql import MySQLDraftStore
    return MySQLDraftStore(db_session)
```

`Server/web/api/repositories/draft_store_dynamo.py`:

```python
"""
DraftStore の DynamoDB 実装。

- テーブル: 環境変数 DRAFTS_TABLE (default: polisjapan-drafts)
  PK: id(N) / GSI: post_status-index (PK: post_status(N), Projection: ALL)
- boto3は同期クライアントを使い、イベントループ阻害を避けるため asyncio.to_thread で呼ぶ
  (motoでそのままテスト可能にする意図もある)
- 日時は ISO 8601 文字列で保存し、Draft では datetime に復元する
- 論理削除は status=0 (MySQL実装と同じ意味論)
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from api.repositories.draft import Draft
from api.utils.time import Time

ID_ALLOCATE_MAX_RETRY = 20
"""採番衝突時(同一epoch秒)の+1リトライ上限"""


class DynamoDraftStore:

    def __init__(self, table_name: Optional[str] = None) -> None:
        self.table_name = table_name or os.environ.get("DRAFTS_TABLE", "polisjapan-drafts")
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    # ---- serialization ----

    @staticmethod
    def _to_item(draft: Draft) -> dict[str, Any]:
        return {
            "id": draft.id,
            "title": draft.title,
            "origin_url": draft.origin_url,
            "origin_html": draft.origin_html,
            "theme_name": draft.theme_name,
            "theme_description": draft.theme_description,
            "theme_comments": draft.theme_comments,
            "theme_category": draft.theme_category,
            "conversation_id": draft.conversation_id,
            "report_id": draft.report_id,
            "post_status": draft.post_status,
            "status": draft.status,
            "create_date": draft.create_date.isoformat() if draft.create_date else None,
            "update_date": draft.update_date.isoformat() if draft.update_date else None,
        }

    @staticmethod
    def _from_item(item: dict[str, Any]) -> Draft:
        def _dt(value):
            return datetime.fromisoformat(value) if value else None
        return Draft(
            id=int(item["id"]),
            title=item.get("title", ""),
            origin_url=item.get("origin_url", ""),
            origin_html=item.get("origin_html", ""),
            theme_name=item.get("theme_name", ""),
            theme_description=item.get("theme_description", ""),
            theme_comments=item.get("theme_comments", ""),
            theme_category=int(item.get("theme_category", 0)),
            conversation_id=item.get("conversation_id", ""),
            report_id=item.get("report_id", ""),
            post_status=int(item.get("post_status", 0)),
            status=int(item.get("status", 1)),
            create_date=_dt(item.get("create_date")),
            update_date=_dt(item.get("update_date")),
        )

    # ---- interface ----

    async def insert_draft(self, *, title: str, origin_url: str, origin_html: str,
                           theme_name: str, theme_description: str, theme_comments: str,
                           theme_category: int, post_status: int) -> Draft:
        now = Time.now()
        draft = Draft(
            id=int(time.time()),
            title=title, origin_url=origin_url, origin_html=origin_html,
            theme_name=theme_name, theme_description=theme_description,
            theme_comments=theme_comments, theme_category=theme_category,
            conversation_id="", report_id="",
            post_status=post_status, status=1,
            create_date=now, update_date=now,
        )

        def _put_with_retry() -> Draft:
            for _ in range(ID_ALLOCATE_MAX_RETRY):
                try:
                    self._table.put_item(
                        Item=self._to_item(draft),
                        ConditionExpression=Attr("id").not_exists(),
                    )
                    return draft
                except self._table.meta.client.exceptions.ConditionalCheckFailedException:
                    draft.id += 1  # 同一秒内の衝突 → +1で再試行
            raise RuntimeError("draft id allocation failed")

        return await asyncio.to_thread(_put_with_retry)

    async def select_by_id(self, draft_id: int) -> Optional[Draft]:
        def _get():
            resp = self._table.get_item(Key={"id": draft_id})
            item = resp.get("Item")
            if not item or int(item.get("status", 1)) != 1:
                return None
            return self._from_item(item)
        return await asyncio.to_thread(_get)

    async def select_all(self) -> list[Draft]:
        def _scan():
            items: list[dict] = []
            kwargs: dict[str, Any] = {"FilterExpression": Attr("status").eq(1)}
            while True:
                resp = self._table.scan(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            drafts = [self._from_item(i) for i in items]
            drafts.sort(key=lambda d: d.id)  # scanは順序不定のためid順で安定化
            return drafts
        return await asyncio.to_thread(_scan)

    async def select_by_post_status(self, post_status: int) -> list[Draft]:
        def _query():
            items: list[dict] = []
            kwargs: dict[str, Any] = {
                "IndexName": "post_status-index",
                "KeyConditionExpression": Key("post_status").eq(post_status),
                "FilterExpression": Attr("status").eq(1),
            }
            while True:
                resp = self._table.query(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            drafts = [self._from_item(i) for i in items]
            drafts.sort(key=lambda d: d.id)
            return drafts
        return await asyncio.to_thread(_query)

    # ---- Task 2 で実装 ----

    async def update_post_status(self, draft: Draft, post_status: int) -> Draft:
        raise NotImplementedError

    async def update_content(self, draft, theme_name, theme_description, theme_comments, theme_category) -> Draft:
        raise NotImplementedError

    async def update_post_info(self, draft: Draft, conversation_id: str, report_id: str, post_status: int) -> Draft:
        raise NotImplementedError

    async def delete_by_id(self, draft_id: int) -> None:
        raise NotImplementedError

    async def commit(self) -> None:
        """DynamoDBは即時反映のためcommitは何もしない(インターフェース互換用)。"""
        return None

    async def rollback(self) -> None:
        """DynamoDBはトランザクション未使用のためrollbackは何もしない(インターフェース互換用)。"""
        return None
```

- [ ] **Step 4: テスト実行（上3件PASS / select_allテストはdelete未実装でFAILのまま）**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest tests/test_draft_store_dynamo.py -v" web
```

Expected: `test_insert_and_select_by_id` `test_select_by_id_not_found_returns_none` `test_insert_id_collision_retries` がPASS、`test_select_all_returns_only_active_sorted` がNotImplementedErrorでFAIL

- [ ] **Step 5: Commit**

```bash
git add Server/web/pyproject.toml Server/web/poetry.lock Server/web/api/repositories Server/web/tests/test_draft_store_dynamo.py
git commit -m "feat: DraftStore抽象化とDynamoDB実装(作成・取得系)を追加"
```

---

### Task 2: DynamoDraftStore（更新・論理削除系）

**Files:**
- Modify: `Server/web/api/repositories/draft_store_dynamo.py`
- Test: `Server/web/tests/test_draft_store_dynamo.py`（追記）

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_draft_store_dynamo.py` の末尾に追加:

```python
async def _make(store, **kw):
    base = dict(title="", origin_url="", origin_html="",
                theme_name="T", theme_description="", theme_comments="", theme_category=1, post_status=2)
    base.update(kw)
    return await store.insert_draft(**base)


async def test_update_post_status(store):
    d = await _make(store)
    updated = await store.update_post_status(d, 3)
    assert updated.post_status == 3  # ローカルにも反映
    loaded = await store.select_by_id(d.id)
    assert loaded.post_status == 3
    assert loaded.update_date >= loaded.create_date


async def test_update_content_partial(store):
    d = await _make(store, theme_name="旧名", theme_category=1)
    await store.update_content(d, theme_name="新名", theme_description=None,
                               theme_comments=None, theme_category=5)
    loaded = await store.select_by_id(d.id)
    assert loaded.theme_name == "新名"
    assert loaded.theme_category == 5
    assert loaded.theme_description == ""  # None指定は更新しない


async def test_update_post_info(store):
    d = await _make(store)
    await store.update_post_info(d, "conv123", "rep456", 3)
    loaded = await store.select_by_id(d.id)
    assert (loaded.conversation_id, loaded.report_id, loaded.post_status) == ("conv123", "rep456", 3)


async def test_delete_by_id_is_logical(store):
    d = await _make(store)
    await store.delete_by_id(d.id)
    assert await store.select_by_id(d.id) is None          # 有効レコードとしては見えない
    assert await store.select_by_post_status(2) == []      # GSI経由でも見えない
    raw = store._table.get_item(Key={"id": d.id})["Item"]  # 物理的には残っている
    assert int(raw["status"]) == 0
```

- [ ] **Step 2: 失敗確認**

Expected: 追加5件（select_allテスト含む）がNotImplementedErrorでFAIL

- [ ] **Step 3: 実装（Task 1のNotImplementedError部分を置き換え）**

```python
    async def _update_fields(self, draft: Draft, fields: dict[str, Any]) -> Draft:
        """指定フィールドを更新し、update_dateを自動付与、ローカルのDraftにも反映する。"""
        fields = dict(fields)
        fields["update_date"] = Time.now()

        expr_names = {f"#f{i}": k for i, k in enumerate(fields)}
        expr_values = {}
        sets = []
        for i, (k, v) in enumerate(fields.items()):
            value = v.isoformat() if isinstance(v, datetime) else v
            expr_values[f":v{i}"] = value
            sets.append(f"#f{i} = :v{i}")

        def _update():
            self._table.update_item(
                Key={"id": draft.id},
                UpdateExpression="SET " + ", ".join(sets),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        await asyncio.to_thread(_update)

        for k, v in fields.items():
            setattr(draft, k, v)
        return draft

    async def update_post_status(self, draft: Draft, post_status: int) -> Draft:
        return await self._update_fields(draft, {"post_status": post_status})

    async def update_content(self, draft: Draft, theme_name, theme_description, theme_comments, theme_category) -> Draft:
        fields = {}
        if theme_name is not None:
            fields["theme_name"] = theme_name
        if theme_description is not None:
            fields["theme_description"] = theme_description
        if theme_comments is not None:
            fields["theme_comments"] = theme_comments
        if theme_category is not None:
            fields["theme_category"] = theme_category
        return await self._update_fields(draft, fields)

    async def update_post_info(self, draft: Draft, conversation_id: str, report_id: str, post_status: int) -> Draft:
        return await self._update_fields(draft, {
            "conversation_id": conversation_id,
            "report_id": report_id,
            "post_status": post_status,
        })

    async def delete_by_id(self, draft_id: int) -> None:
        draft = await self.select_by_id(draft_id)
        if draft is None:
            return
        await self._update_fields(draft, {"status": 0})
```

- [ ] **Step 4: 全テストPASS確認 + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest tests/test_draft_store_dynamo.py -v" web
git add Server/web/api/repositories/draft_store_dynamo.py Server/web/tests/test_draft_store_dynamo.py
git commit -m "feat: DynamoDraftStoreの更新・論理削除を実装"
```

---

### Task 3: MySQLDraftStore + factory + DATA_BACKEND設定

**Files:**
- Create: `Server/web/api/repositories/draft_store_mysql.py`
- Modify: `Server/web/api/configs/constants.py`（`DATA_BACKEND = "mysql"` を追記）
- Modify: `Server/web/api/configs/serverless/constants.py`（`load_from_env()` の戻り値に `"DATA_BACKEND": "dynamodb"` を追記し、テストの期待値にも追加）
- Test: `Server/web/tests/test_draft_store_factory.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_draft_store_factory.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import api.configs as configs
from api.repositories import create_draft_store
from api.repositories.draft import Draft
from api.repositories.draft_store_dynamo import DynamoDraftStore
from api.repositories.draft_store_mysql import MySQLDraftStore


def test_factory_returns_mysql_by_default(monkeypatch):
    monkeypatch.setattr(configs.constants, "DATA_BACKEND", "mysql", raising=False)
    store = create_draft_store(db_session=MagicMock())
    assert isinstance(store, MySQLDraftStore)


def test_factory_returns_dynamo_when_configured(monkeypatch):
    monkeypatch.setattr(configs.constants, "DATA_BACKEND", "dynamodb", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")
    from moto import mock_aws
    with mock_aws():
        store = create_draft_store()
        assert isinstance(store, DynamoDraftStore)


async def test_mysql_store_delegates_to_cruds():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    store = MySQLDraftStore(db)

    orm_row = MagicMock(id=1, post_status=2)
    with patch("api.repositories.draft_store_mysql.cruds") as cruds_mock:
        cruds_mock.TDraft.select_by_post_status = AsyncMock(return_value=[orm_row])
        result = await store.select_by_post_status(2)
        cruds_mock.TDraft.select_by_post_status.assert_awaited_once_with(db, 2)
        assert result == [orm_row]

    await store.commit()
    db.commit.assert_awaited_once()
    await store.rollback()
    db.rollback.assert_awaited_once()
```

- [ ] **Step 2: 失敗確認**

Expected: `ModuleNotFoundError: No module named 'api.repositories.draft_store_mysql'`

- [ ] **Step 3: 実装**

`Server/web/api/repositories/draft_store_mysql.py`:

```python
"""
DraftStore の MySQL 実装。既存の cruds.TDraft への薄い委譲。

戻り値はORMオブジェクト(tables.TDraft)そのままだが、属性名は
repositories.draft.Draft と同一のため、ルーター/レスポンスモデルからは同じに見える。
"""
from __future__ import annotations

from typing import Optional

from api import cruds


class MySQLDraftStore:

    def __init__(self, db_session) -> None:
        if db_session is None:
            raise ValueError("MySQLDraftStore requires db_session")
        self.db = db_session

    async def insert_draft(self, *, title, origin_url, origin_html,
                           theme_name, theme_description, theme_comments,
                           theme_category, post_status):
        return await cruds.TDraft.insert(
            db=self.db, title=title, origin_url=origin_url, origin_html=origin_html,
            theme_name=theme_name, theme_description=theme_description,
            theme_comments=theme_comments, theme_category=theme_category,
            post_status=post_status,
        )

    async def select_by_id(self, draft_id: int):
        return await cruds.TDraft.select_by_id(self.db, draft_id)

    async def select_all(self):
        return await cruds.TDraft.select_all(self.db)

    async def select_by_post_status(self, post_status: int):
        return await cruds.TDraft.select_by_post_status(self.db, post_status)

    async def update_post_status(self, draft, post_status: int):
        return await cruds.TDraft.update_post_status(self.db, draft, post_status)

    async def update_content(self, draft, theme_name, theme_description, theme_comments, theme_category):
        return await cruds.TDraft.update_content(self.db, draft, theme_name, theme_description, theme_comments, theme_category)

    async def update_post_info(self, draft, conversation_id: str, report_id: str, post_status: int):
        return await cruds.TDraft.update_post_info(self.db, draft, conversation_id, report_id, post_status)

    async def delete_by_id(self, draft_id: int) -> None:
        await cruds.TDraft.delete_by_id(self.db, draft_id)

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()
```

`configs/constants.py`（基底）に追記:

```python
DATA_BACKEND = "mysql"
"""下書きデータの保存先: mysql | dynamodb。serverless環境のみdynamodbに上書きされる"""
```

`configs/serverless/constants.py` の `load_from_env()` 戻り値dictに追記:

```python
        "DATA_BACKEND": "dynamodb",
```

`tests/test_configs_serverless.py` の `test_load_constants_from_env` にアサート追記:

```python
    assert c["DATA_BACKEND"] == "dynamodb"
```

- [ ] **Step 4: 全テストPASS確認 + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
git add Server/web/api/repositories/draft_store_mysql.py Server/web/api/configs/constants.py Server/web/api/configs/serverless/constants.py Server/web/tests/test_draft_store_factory.py Server/web/tests/test_configs_serverless.py
git commit -m "feat: MySQLDraftStoreとDATA_BACKENDによるストア切替を追加"
```

---

### Task 4: ルーター/リクエスト処理の差し替え

**Files:**
- Modify: `Server/web/api/core/common_service.py`
- Modify: `Server/web/api/core/common_route.py`
- Modify: `Server/web/api/routers/batch.py`
- Modify: `Server/web/api/routers/admin.py`
- Modify: `Server/web/api/routers/theme.py`

方針: ルーター内の `cruds.TDraft.xxx(service.db_session, ...)` を `service.draft_store.xxx(...)` に、`service.db_session.commit()/rollback()` を `service.draft_store.commit()/rollback()` に置き換える。`common_route` は DATA_BACKEND=mysql のときだけDBセッションを開く。

- [ ] **Step 1: common_service.py に属性を追加**

`CommonService` のクラス属性宣言部（`s3: StorageS3` の下）に追加:

```python
    draft_store: "DraftStore"
    """テーマ下書きのデータストア。common_routeがリクエスト毎に設定する。"""
```

ファイル先頭のimportに追加（循環import回避のためTYPE_CHECKINGで）:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from api.repositories.draft import DraftStore
```

- [ ] **Step 2: common_route.py のセッション制御を書き換え**

`custom_route_handler` 内の「DBコネクション開始」以降（54〜94行）を次の構造に置き換える:

```python
            # DBコネクション開始（mysqlバックエンドの場合のみ）
            use_mysql = getattr(configs.constants, "DATA_BACKEND", "mysql") == "mysql"

            if use_mysql:
                async with async_session() as db:
                    return await self.handle_with_service(request, original_route_handler, db, is_user_auth_api)
            else:
                # serverless(dynamodb)ではRDBを使わない。ユーザー認証APIはRDB前提のため未対応
                if is_user_auth_api:
                    return await self.generate_api_error_response(request, UserAuthError())
                return await self.handle_with_service(request, original_route_handler, None, is_user_auth_api)
```

同クラスに新メソッド `handle_with_service` を追加（既存54〜94行のロジックを移設し、store生成を追加）:

```python
    async def handle_with_service(self, request: Request, original_route_handler: Callable, db, is_user_auth_api: bool):
        """サービス初期化〜API本体実行〜後処理までの共通フロー。dbはmysql時のみ非None。"""
        from api.repositories import create_draft_store

        # サービス初期化
        request.state.service = await get_service(request.state.router_name)
        request.state.service.db_session = db
        request.state.service.draft_store = create_draft_store(db)

        # ユーザー認証通信の場合はチェック（既存ロジックをそのまま移設）
        if is_user_auth_api:
            session_id = request.cookies.get("session_id")
            t_account = await cruds.TAccount.select_by_session_id(request.state.service.db_session, session_id)

            # アカウントがない場合は、セッション情報が間違っているのでエラー
            if not t_account:
                return await self.generate_api_error_response(request, UserAuthError())

            # ログインしたことがないユーザーの場合、先にログインしてセッションを発行しなければユーザー認証通信は使えない
            if str(t_account.session_id) == "":
                return await self.generate_api_error_response(request, UserAuthError())

            t_user = await cruds.TUser.select_by_id(request.state.service.db_session, t_account.t_user_id)
            t_user_add = await cruds.TUserAdd.select_by_t_user_id(request.state.service.db_session, t_account.t_user_id)

            # アカウント情報があって、他のユーザー関連情報がない場合は不正なデータなので処理終了
            if not t_user or not t_user_add:
                return await self.generate_api_error_response(request, UnknownError())

            request.state.service.t_user = t_user
            request.state.service.t_account = t_account
            request.state.service.t_user_add = t_user_add

        # API本体へ
        try:
            response = await original_route_handler(request)
        except ApiError as err:
            return await self.generate_api_error_response(request, err)
        except Exception as exc:
            return await self.generate_generic_error_response(request, exc)

        Logger.info(f"-> API処理終了")
        await self.finalize_request(request)
        return response
```

`finalize_request` のDBクローズをNone安全にする:

```python
        # S3クライアントのセッションを終了
        await request.state.service.s3.close()
        # DBセッションを終了（mysqlバックエンドの場合のみ存在）
        if request.state.service.db_session is not None:
            await request.state.service.db_session.close()
```

- [ ] **Step 3: routers/batch.py の置き換え（3箇所）**

- `create_all` 147行: `t_draft_list = await cruds.TDraft.select_by_post_status(service.db_session, types.PostStatus.APPROVED.value)` → `t_draft_list = await service.draft_store.select_by_post_status(types.PostStatus.APPROVED.value)`
- `create_all` 180〜187行のtry/commitブロック:

```python
    try:
        for t_draft in t_draft_list:
            await service.draft_store.update_post_info(t_draft, t_draft.conversation_id, t_draft.report_id, types.PostStatus.POSTED.value)

        await service.draft_store.commit()
    except Exception as e:
        await service.draft_store.rollback()
        raise e
```

- `delete` 224行: `t_draft = await cruds.TDraft.select_by_id(service.db_session, request_body.t_draft_id)` → `t_draft = await service.draft_store.select_by_id(request_body.t_draft_id)`
- `delete` 252〜260行:

```python
    try:
        # 対象下書き情報を論理削除
        if t_draft:
            await service.draft_store.delete_by_id(t_draft.id)

        await service.draft_store.commit()
    except Exception as e:
        await service.draft_store.rollback()
        raise e
```

- ファイル先頭の `import api.cruds as cruds` は他に使用箇所が無くなるため削除。

- [ ] **Step 4: routers/admin.py の置き換え（info/approve/edit）**

- `info` 51行: `await cruds.TDraft.select_all(service.db_session)` → `await service.draft_store.select_all()`
- `approve` 93行: `await cruds.TDraft.select_by_id(service.db_session, request_body.t_draft_id)` → `await service.draft_store.select_by_id(request_body.t_draft_id)`
- `approve` 102行: `await cruds.TDraft.update_post_status(service.db_session, t_draft, types.PostStatus.APPROVED.value)` → `await service.draft_store.update_post_status(t_draft, types.PostStatus.APPROVED.value)`
- `edit` 151行: 同様に `select_by_id` を置き換え
- `edit` 160行: `await cruds.TDraft.update_content(service.db_session, t_draft, ...)` → `await service.draft_store.update_content(t_draft, request_body.theme_name, request_body.theme_description, request_body.theme_comments, request_body.theme_category)`
- admin.py 内の `service.db_session.commit()` / `rollback()` をすべて `service.draft_store.commit()` / `rollback()` に置き換え
- `import api.cruds as cruds` が未使用になれば削除

- [ ] **Step 5: routers/theme.py の post_draft を置き換え**

```python
    # 3.DB更新処理実行
    try:
        # 送信された内容を、下書きの新規レコードとして挿入
        t_draft = await service.draft_store.insert_draft(
            title = "",
            origin_url = "",
            origin_html = "",
            theme_name = request_body.theme,
            theme_description = request_body.description,
            theme_comments = request_body.comments,
            theme_category = request_body.category,
            post_status = types.PostStatus.APPROVED.value,
        )
        await service.draft_store.commit()
    except Exception as e:
        await service.draft_store.rollback()
        raise e
```

`import api.cruds as cruds` が未使用になれば削除。

- [ ] **Step 6: 検証（ユニット + MySQL経路のDocker回帰）**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
grep -rn "cruds.TDraft" Server/web/api/routers && echo "NG: 置き換え漏れ" || echo "OK"
# MySQL経路の回帰（healthcheck + テーマ投稿→admin/infoで見えることをcurlで確認）
OVR=<scratchpad>/compose-test-ports.yml
docker compose -f docker-compose.yml -f "$OVR" up -d && sleep 15
curl -s http://localhost:8090/batch/healthcheck
# theme/post_draft と admin/info はアクセスキーが必要なため、configs/localhostの値を使って手元で確認する
#（アクセスキーの値はコマンド履歴に残さないよう、環境変数経由で読み込むこと）
docker compose -f docker-compose.yml -f "$OVR" down
```

Expected: 全テストPASS / 置き換え漏れなし / healthcheck `{"is_success":true}` / post_draft→admin/infoの一連がMySQL経路で動作

- [ ] **Step 7: Commit**

```bash
git add Server/web/api/core/common_service.py Server/web/api/core/common_route.py Server/web/api/routers/batch.py Server/web/api/routers/admin.py Server/web/api/routers/theme.py
git commit -m "refactor: 下書きアクセスをDraftStore経由に統一しserverlessでRDB非依存に"
```

---

### Task 5: データ移行スクリプト

**Files:**
- Create: `Server/web/scripts/__init__.py`（空）
- Create: `Server/web/scripts/migrate_drafts_to_dynamodb.py`
- Test: `Server/web/tests/test_migrate_script.py`

入力は本番MySQLからエクスポートしたJSON（カットオーバーRunbookでSSH経由取得: `docker exec PolisJAPAN_db mysql -u... -p... app_db -e "SELECT ... FROM t_draft" --json` 相当）。`origin_html` は移行対象外（設計書§3.2）。

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_migrate_script.py`:

```python
import json

import boto3
import pytest
from moto import mock_aws

from scripts.migrate_drafts_to_dynamodb import row_to_item, migrate, verify

TABLE = "polisjapan-drafts-test"

SAMPLE_ROWS = [
    {
        "id": 5, "title": "t", "origin_url": "u", "origin_html": "<html>大きいHTML</html>",
        "theme_name": "名前", "theme_description": "説明", "theme_comments": "a###br###b",
        "theme_category": 3, "conversation_id": "c5", "report_id": "r5",
        "post_status": 3, "status": 1,
        "create_date": "2026-01-02 03:04:05", "update_date": "2026-01-03 03:04:05",
    },
    {
        "id": 6, "title": "", "origin_url": "", "origin_html": "",
        "theme_name": "削除済み", "theme_description": "", "theme_comments": "",
        "theme_category": 1, "conversation_id": "", "report_id": "",
        "post_status": 101, "status": 0,
        "create_date": "2026-02-02 03:04:05", "update_date": "2026-02-03 03:04:05",
    },
]


def test_row_to_item_excludes_origin_html_and_converts_dates():
    item = row_to_item(SAMPLE_ROWS[0])
    assert item["id"] == 5
    assert item["origin_html"] == ""            # LONGTEXTは移行しない(アーカイブに残る)
    assert item["create_date"] == "2026-01-02T03:04:05"  # MySQL形式 → ISO 8601
    assert item["post_status"] == 3
    assert item["status"] == 1


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-3")
        client.create_table(
            TableName=TABLE,
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "N"},
                {"AttributeName": "post_status", "AttributeType": "N"},
            ],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "post_status-index",
                "KeySchema": [{"AttributeName": "post_status", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="ap-northeast-3").Table(TABLE)


def test_migrate_and_verify(table, tmp_path):
    src = tmp_path / "t_draft.json"
    src.write_text(json.dumps(SAMPLE_ROWS, ensure_ascii=False))

    result = migrate(str(src), TABLE)
    assert result == {"total": 2, "written": 2}

    # 論理削除済み(status=0)も含めて全行移行される（履歴保全のため）
    ok, report = verify(str(src), TABLE)
    assert ok is True
    assert report["source_count"] == 2
    assert report["table_count"] == 2
    assert report["mismatched_ids"] == []
```

- [ ] **Step 2: 失敗確認**

Expected: `ModuleNotFoundError: No module named 'scripts'`（conftest.pyのsys.path挿入でServer/web直下は解決済みのため、scripts/__init__.py作成後はimport可能になる）

- [ ] **Step 3: 実装**

`Server/web/scripts/__init__.py` — 空ファイル。

`Server/web/scripts/migrate_drafts_to_dynamodb.py`:

```python
"""
t_draft(MySQL) → DynamoDB 移行スクリプト。

使い方:
  1. 本番MySQLからJSONエクスポート（カットオーバーRunbook参照）:
     docker exec PolisJAPAN_db sh -c 'mysql -uapp_user -p"$MYSQL_PASSWORD" app_db \
       -e "SELECT * FROM t_draft" --batch' などで取得しJSON化
  2. poetry run python -m scripts.migrate_drafts_to_dynamodb t_draft.json polisjapan-drafts
  3. 末尾に検証結果（件数照合・全属性突合）が出力される。NGなら終了コード1

方針:
  - origin_html は移行しない（休眠スクレイピング機能用の大容量LONGTEXT。全量はS3アーカイブに残る）
  - status=0（論理削除済み）も含め全行を移行する（削除履歴の保全）
  - 日時は "YYYY-MM-DD HH:MM:SS" → ISO 8601 に変換
"""
import json
import sys

import boto3

MIGRATE_FIELDS = [
    "id", "title", "origin_url", "theme_name", "theme_description",
    "theme_comments", "theme_category", "conversation_id", "report_id",
    "post_status", "status",
]
INT_FIELDS = {"id", "theme_category", "post_status", "status"}
DATE_FIELDS = ["create_date", "update_date"]


def _to_iso(mysql_datetime: str) -> str:
    """'2026-01-02 03:04:05' → '2026-01-02T03:04:05'（既にISOならそのまま）。"""
    return mysql_datetime.replace(" ", "T") if mysql_datetime else None


def row_to_item(row: dict) -> dict:
    """MySQLの1行をDynamoDBアイテムに変換する。origin_htmlは空文字に落とす。"""
    item = {}
    for f in MIGRATE_FIELDS:
        value = row.get(f)
        item[f] = int(value) if f in INT_FIELDS else (value if value is not None else "")
    item["origin_html"] = ""
    for f in DATE_FIELDS:
        item[f] = _to_iso(row.get(f))
    return item


def migrate(source_json_path: str, table_name: str) -> dict:
    """JSONファイルの全行をDynamoDBにbatch書き込みする。"""
    rows = json.loads(open(source_json_path, encoding="utf-8").read())
    table = boto3.resource("dynamodb").Table(table_name)
    written = 0
    with table.batch_writer(overwrite_by_pkeys=["id"]) as batch:
        for row in rows:
            batch.put_item(Item=row_to_item(row))
            written += 1
    return {"total": len(rows), "written": written}


def verify(source_json_path: str, table_name: str) -> tuple[bool, dict]:
    """件数照合 + 全行の属性突合（origin_html以外）を行う。"""
    rows = json.loads(open(source_json_path, encoding="utf-8").read())
    table = boto3.resource("dynamodb").Table(table_name)

    items: dict[int, dict] = {}
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            items[int(item["id"])] = item
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    mismatched = []
    for row in rows:
        expected = row_to_item(row)
        actual = items.get(int(row["id"]))
        if actual is None:
            mismatched.append(int(row["id"]))
            continue
        for key, value in expected.items():
            actual_value = actual.get(key)
            if key in INT_FIELDS:
                actual_value = int(actual_value)
            if actual_value != value:
                mismatched.append(int(row["id"]))
                break

    report = {
        "source_count": len(rows),
        "table_count": len(items),
        "mismatched_ids": mismatched,
    }
    ok = len(rows) == len(items) and not mismatched
    return ok, report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m scripts.migrate_drafts_to_dynamodb <t_draft.json> <table_name>")
        sys.exit(2)
    source, table_name = sys.argv[1], sys.argv[2]

    print(f"migrate: {source} -> {table_name}")
    print(json.dumps(migrate(source, table_name), ensure_ascii=False))

    ok, report = verify(source, table_name)
    print(json.dumps(report, ensure_ascii=False))
    print("VERIFY OK" if ok else "VERIFY FAILED")
    sys.exit(0 if ok else 1)
```

- [ ] **Step 4: 全テストPASS確認 + Commit**

```bash
cd Server && docker compose run --rm --no-deps --entrypoint "poetry run pytest -v" web
git add Server/web/scripts Server/web/tests/test_migrate_script.py
git commit -m "feat: t_draftのDynamoDB移行スクリプト（変換+投入+検証）を追加"
```

---

## 後続プラン（本プランのスコープ外）

- バッチLambda化編（batch-update / batch-create のLambdaエントリポイント、1起動1件処理）
- Terraform編（`polisjapan-drafts` テーブル・GSI・PITRの実リソース作成を含む）

## Self-Review 結果

- 設計書§2.1「DynamoDB drafts」との対応: PK id(N)✅ GSI post_status-index✅ 論理削除の意味論維持✅ origin_html除外✅ PITRはTerraform編で設定（テーブル作成側の責務）✅
- serverless時のRDB非接続: common_routeの分岐で対応（Task 4）✅。ユーザー認証API（未マウント）はserverlessでは明示エラー✅
- 型整合: DraftStoreの全メソッドシグネチャはTask 1定義とTask 3ラッパー/Task 4呼び出しで一致。id は int で統一（既存スキーマ `t_draft_id: int` と互換）✅
- admin/info のレスポンス: DynamoDraftStoreは `Draft` dataclassを返し、`TDraftModel(from_attributes)` の検証を通る（属性名一致・create_dateはdatetime復元）✅
- 移行スクリプトは status=0 も含め全行移行（削除履歴保全）、検証は件数+全属性突合✅
