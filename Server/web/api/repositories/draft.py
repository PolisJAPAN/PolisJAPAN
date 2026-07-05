"""
テーマ下書き(t_draft相当)のデータアクセス抽象化層。

ルーターはこのモジュールの DraftStore インターフェースにのみ依存し、
実体は configs.constants.DATA_BACKEND で mysql / dynamodb を切り替える。
"""
from __future__ import annotations

from dataclasses import dataclass
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
