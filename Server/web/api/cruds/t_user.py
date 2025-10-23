from datetime import datetime
from api.models import tables
from api.core.common_cruds import CommonCruds
from sqlalchemy.ext.asyncio import AsyncSession
import api.utils as utils

class TUser(CommonCruds[tables.TUser]):
    """
    t_user テーブルに対応するCRUD操作クラス。

    CommonCrudsを継承し、ユーザー基本情報（名前、プロフィール、ログイン情報など）の
    登録・更新・取得処理を提供する。
    """
    
    model = tables.TUser
    """操作対象となるSQLAlchemyモデル（t_userテーブル）"""
    
    @classmethod
    async def insert(
        cls,
        db: AsyncSession,
        name: str,
        profile: str,
    ) -> tables.TUser:
        """
        TUser用の新規登録メソッド（dictではなく明示的な引数指定）。

        Args:
            db (AsyncSession): 非同期DBセッション。
            name (str): 登録するユーザー名。
            profile (str): 登録するプロフィール情報。

        Returns:
            tables.TUser: 登録されたユーザーオブジェクト。
        """

        obj = {
            "name" : name,
            "profile" : profile,
        }
        result = await cls._insert(db, obj)
        return result
    
    @classmethod
    async def update_last_login_date(
        cls,
        db: AsyncSession,
        t_user: tables.TUser,
        last_login_date: datetime,
    ) -> tables.TUser:
        """
        指定したユーザーの最終ログイン日時を更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_user (tables.TUser): 更新対象のユーザーオブジェクト。
            last_login_date (datetime): 更新する最終ログイン日時。

        Returns:
            tables.TUser: 更新後のユーザーオブジェクト。
        """

        set = {
            "last_login_date" : last_login_date,
        }
        result = await cls.update(db, t_user, set)
        return result

