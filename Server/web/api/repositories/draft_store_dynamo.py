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
