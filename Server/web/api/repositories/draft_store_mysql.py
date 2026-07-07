"""
DraftStore の MySQL 実装。既存の cruds.TDraft への薄い委譲。

戻り値はORMオブジェクト(tables.TDraft)そのままだが、属性名は
repositories.draft.Draft と同一のため、ルーター/レスポンスモデルからは同じに見える。
"""
from __future__ import annotations

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
