from sqlalchemy.ext.asyncio import AsyncSession

import api.utils as utils
from api.core.common_cruds import CommonCruds
from api.models import tables


class TUserAdd(CommonCruds[tables.TUser]):
    """
    t_user_add テーブルに対応するCRUD操作クラス。

    CommonCrudsを継承し、ユーザー追加情報（プロンプトや拡張設定など）を扱う。
    主にユーザー登録時やプロフィール拡張時に使用される。
    """
    
    model = tables.TUserAdd
    """操作対象となるSQLAlchemyモデル（t_user_addテーブル）"""
    
    @classmethod
    async def insert(
        cls,
        db: AsyncSession,
        t_user_id: int,
    ) -> tables.TUserAdd:
        """
        TUserAdd用の新規登録メソッド（dictでなく明示的な引数指定）。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_user_id (int): 登録対象のユーザーID。

        Returns:
            tables.TUserAdd: 登録されたユーザー追加情報オブジェクト。
        """

        obj = {
            "t_user_id" : t_user_id,
            "user_prompt" : "",
        }
        result = await cls._insert(db, obj)
        return result
    
    @classmethod
    async def update_data(
        cls,
        db: AsyncSession,
        id: int,
        set: dict,
    ) -> int:
        """
        IDを指定してユーザー追加情報を一括更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            id (int): 更新対象レコードの主キーID。
            set (dict): 更新内容（カラム名→値の辞書）。

        Returns:
            int: 更新件数（rowcount）。
        """

        where = {
            "id" : id,
        }
        result = await cls._update(db, where, set)
        return result

