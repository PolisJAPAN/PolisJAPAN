from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

import api.models.types as types
import api.utils as utils
from api.core.common_cruds import CommonCruds
from api.models import tables


class TDraft(CommonCruds[tables.TDraft]):
    """
    t_draft テーブルに対応するCRUD操作クラス。

    下書きテーマ情報（タイトル、参照URL、説明文など）の登録・更新・検索を管理する。
    CommonCrudsを継承し、t_draftテーブル特有の更新処理を実装する。
    """
    
    model = tables.TDraft
    """操作対象となるSQLAlchemyモデル（t_draftテーブル）"""
    
    @classmethod
    async def insert(
        cls,
        db: AsyncSession,
        title: str,
        origin_url: str,
        origin_html: str,
        theme_name: str,
        theme_description: str,
        theme_comments: str,
        theme_category: int,
    ) -> tables.TDraft:
        """
        TDraft用の新規登録メソッド。

        Args:
            db (AsyncSession): 非同期DBセッション。
            title (str): テーマのタイトル。
            origin_url (str): 参照元URL。
            origin_html (str): 参照HTML（記事本文など）。
            theme_name (str): テーマ名。
            theme_description (str): テーマ説明。
            theme_comments (str): コメント内容。
            theme_category (int): カテゴリ番号。

        Returns:
            tables.TDraft: 登録された下書きオブジェクト。
        """

        obj = {
            "title" : title,
            "origin_url" : origin_url,
            "origin_html" : origin_html,
            "theme_name" : theme_name,
            "theme_description" : theme_description,
            "theme_comments" : theme_comments,
            "theme_category" : theme_category,
            "conversation_id" : "",
            "report_id" : "",
            "post_status" : types.PostStatus.GENERATED.value,
        }
        result = await cls._insert(db, obj)
        return result
    
    @classmethod
    async def select_by_post_status(cls, db: AsyncSession, post_status: int) -> list[tables.TDraft]:
        """
        投稿ステータスを指定して複数件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            post_status (int): 投稿ステータスコード。

        Returns:
            list[tables.TDraft]: 該当する下書きオブジェクトのリスト。
        """
        
        where = {
            "post_status" : post_status
        }
        
        return await cls._select_list(db, where)
    
    @classmethod
    async def update_post_status(
        cls,
        db: AsyncSession,
        t_draft: tables.TDraft,
        post_status: int,
    ) -> tables.TDraft:
        """
        指定した下書きの投稿ステータスを更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_draft (tables.TDraft): 更新対象の下書きオブジェクト。
            post_status (int): 更新する投稿ステータスコード。

        Returns:
            tables.TDraft: 更新後の下書きオブジェクト。
        """

        set = {
            "post_status" : post_status,
        }
        result = await cls.update(db, t_draft, set)
        return result
    
    @classmethod
    async def update_list_post_status(
        cls,
        db: AsyncSession,
        t_draft_list: list[tables.TDraft],
        post_status: int,
    ) -> list[tables.TDraft]:
        """
        複数の下書きに対して投稿ステータスを一括更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_draft_list (list[tables.TDraft]): 更新対象の下書きリスト。
            post_status (int): 更新する投稿ステータスコード。

        Returns:
            list[tables.TDraft]: 更新後の下書きオブジェクトリスト。
        """
        
        set = {
            "post_status" : post_status,
        }
        result = await cls._update_list(db, t_draft_list, set)
        return result
    
    @classmethod
    async def update_data(
        cls,
        db: AsyncSession,
        t_draft: tables.TDraft,
        title: str,
        origin_url: str,
        origin_html: str,
        theme_name: str,
        theme_description: str,
        theme_comments: str,
        theme_category: int,
    ) -> tables.TDraft:
        """
        下書き全体の変更可能なデータを一括更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_draft (tables.TDraft): 更新対象の下書きオブジェクト。
            title (str): テーマタイトル。
            origin_url (str): 参照URL。
            origin_html (str): 参照HTML。
            theme_name (str): テーマ名。
            theme_description (str): テーマ説明。
            theme_comments (str): コメント。
            theme_category (int): カテゴリ番号。

        Returns:
            tables.TDraft: 更新後の下書きオブジェクト。
        """


        set = {
            "title" : title,
            "origin_url" : origin_url,
            "origin_html" : origin_html,
            "theme_name" : theme_name,
            "theme_description" : theme_description,
            "theme_comments" : theme_comments,
            "theme_category" : theme_category,
        }
        result = await cls.update(db, t_draft, set)
        return result
    
    @classmethod
    async def update_content(
        cls,
        db: AsyncSession,
        t_draft: tables.TDraft,
        theme_name: Optional[str],
        theme_description: Optional[str],
        theme_comments: Optional[str],
        theme_category: Optional[int],
    ) -> tables.TDraft:
        """
        テーマコンテンツ部分のみを更新するメソッド。

        Noneでない引数のみ更新対象とする。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_draft (tables.TDraft): 更新対象の下書きオブジェクト。
            theme_name (Optional[str]): 新しいテーマ名。
            theme_description (Optional[str]): 新しいテーマ説明。
            theme_comments (Optional[str]): 新しいコメント。
            theme_category (Optional[int]): 新しいカテゴリ番号。

        Returns:
            tables.TDraft: 更新後の下書きオブジェクト。
        """
        set = {}
        
        if theme_name != None:
            set["theme_name"] = theme_name
        
        if theme_description != None:
            set["theme_description"] = theme_description
        
        if theme_comments != None:
            set["theme_comments"] = theme_comments
        
        if theme_category != None:
            set["theme_category"] = theme_category

        result = await cls.update(db, t_draft, set)
        return result