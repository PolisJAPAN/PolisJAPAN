from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

import api.utils as utils
from api.core.common_cruds import CommonCruds
from api.models import tables


class TAccount(CommonCruds[tables.TUser]):
    """
    t_account テーブルに対応するCRUD操作クラス。

    CommonCrudsを継承し、アカウント情報の登録・検索・更新処理を提供する。
    """
    
    model = tables.TAccount
    """操作対象となるSQLAlchemyモデル（t_accountテーブル）"""
    
    @classmethod
    async def insert(
        cls,
        db: AsyncSession,
        t_user_id: int,
        mail: str,
        password: str,
    ) -> tables.TAccount:
        """
        TAccount用の新規登録メソッド

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_user_id (int): 対応するユーザーID。
            mail (str): メールアドレス。
            password (str): ハッシュ化済みパスワード。

        Returns:
            tables.TAccount: 登録されたアカウントオブジェクト。
        """

        obj = {
            "t_user_id" : t_user_id,
            "mail" : mail,
            "password" : password,
            "session_id" : "",
        }
        result = await cls._insert(db, obj)
        return result
    
    @classmethod
    async def select_by_mail(cls, db: AsyncSession, mail:str) -> tables.TAccount:
        """
        メールアドレスを指定して1件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            mail (str): 検索対象のメールアドレス。

        Returns:
            tables.TAccount: 一致するアカウントオブジェクト。存在しない場合はNone。
        """
        
        where = {
            "mail" : mail
        }
        
        return await cls._select(db, where)
    
    @classmethod
    async def select_by_session_id(cls, db: AsyncSession, session_id:str) -> tables.TAccount:
        """
        セッションIDを指定して1件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            session_id (str): 検索対象のセッションID。

        Returns:
            tables.TAccount: 一致するアカウントオブジェクト。存在しない場合はNone。
        """
        
        where = {
            "session_id" : session_id
        }
        
        return await cls._select(db, where)
    
    @classmethod
    async def update_session_id(
        cls,
        db: AsyncSession,
        t_account: tables.TAccount,
        session_id: str,
    ) -> tables.TAccount:
        """
        指定したアカウントのセッションIDを更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_account (tables.TAccount): 更新対象のアカウントオブジェクト。
            session_id (str): 新しいセッションID。

        Returns:
            tables.TAccount: 更新後のアカウントオブジェクト。
        """

        set = {
            "session_id" : session_id,
        }
        result = await cls.update(db, t_account, set)
        return result
    
    @classmethod
    async def update_last_api_date(
        cls,
        db: AsyncSession,
        t_account: tables.TAccount,
        last_api_date: datetime,
    ) -> int:
        """
        指定したアカウントの最終API実行日時を更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_account (tables.TAccount): 更新対象のアカウントオブジェクト。
            last_api_date (datetime): 更新する日時（通常は現在時刻）。

        Returns:
            int: 更新されたレコード数。
        """

        set = {
            "last_api_date" : last_api_date,
        }
        result = await cls.update(db, t_account, set)
        return result
