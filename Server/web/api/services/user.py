import secrets
from typing import Optional

from api import cruds
from api.core.common_service import CommonService
from api.models import tables

class UserService(CommonService):
    """
    ユーザー操作関連の処理を集約したサービスクラス
    """
    
    async def generate_unique_session_id(self, db_session) -> str:
        """
        一意なセッションIDを生成する。

        既存のセッションIDと重複しない128文字の16進乱数文字列を作成する。
        重複が見つかった場合は再生成を繰り返す。

        Args:
            db_session (AsyncSession): 非同期DBセッション。

        Returns:
            str: 一意なセッションID文字列。
        """
        
        while True:
            new_session_id: str = secrets.token_hex(64)  # 128文字のランダム16進文字列

            # 重複チェック
            existing = await cruds.TAccount.select_by_session_id(db_session, new_session_id)
            if existing is None:
                return new_session_id

    def get_t_user_edit_data(self, name, profile) -> Optional[dict]:
        """
        ユーザー基本情報の更新差分を抽出する。

        現在の `t_user` の値と比較し、変更があったフィールドのみ
        set辞書として返す。変更がない場合は `None` を返す。

        Args:
            name (str): 新しいユーザー名。
            profile (str): 新しいプロフィール。

        Returns:
            Optional[dict]: 変更フィールドの辞書。変更なしの場合はNone。
        """
        
        set_dict : dict = {}
        
        if name != self.t_user.name:
            set_dict["name"] = name
        
        if profile != self.t_user.profile:
            set_dict["profile"] = profile
        
        # 更新データがない場合はNoneを返却
        if len(set_dict.keys()) == 0:
            return None
        
        return set_dict
    

    def get_t_user_add_edit_data(self, user_prompt):
        """
        ユーザー追加情報（t_user_add）の更新差分を抽出する。

        現在の `t_user_add` の値と比較し、変更があった場合のみ
        set辞書として返す。変更がない場合は `None` を返す。

        Args:
            user_prompt (str): 新しいプロンプト文字列。

        Returns:
            Optional[dict]: 変更フィールドの辞書。変更なしの場合はNone。
        """
        
        set_dict : dict = {}
        
        if user_prompt != self.t_user_add.user_prompt:
            set_dict["user_prompt"] = user_prompt
            
        # 更新データがない場合はNoneを返却
        if len(set_dict.keys()) == 0:
            return None
        
        return set_dict
    

    def get_updateded_t_user(self, name, profile) -> tables.TUser:
        """
        ユーザー情報をローカルで更新し、更新後のオブジェクトを返す。

        DB更新は行わず、現在保持している `t_user` オブジェクトを直接書き換える。

        Args:
            name (str): 新しいユーザー名。
            profile (str): 新しいプロフィール。

        Returns:
            tables.TUser: 更新後のユーザーオブジェクト。
        """

        
        if name != self.t_user.name:
            self.t_user.name = name
        
        if profile != self.t_user.profile:
            self.t_user.profile = profile
        
        return self.t_user
    

    def get_updateded_t_user_add(self, user_prompt) -> tables.TUserAdd:
        """
        ユーザー追加情報をローカルで更新し、更新後のオブジェクトを返す。

        DB更新は行わず、現在保持している `t_user_add` オブジェクトを直接書き換える。

        Args:
            user_prompt (str): 新しいプロンプト文字列。

        Returns:
            tables.TUserAdd: 更新後のユーザー追加情報オブジェクト。
        """
        
        if user_prompt != self.t_user_add.user_prompt:
            self.t_user_add.user_prompt = user_prompt
        
        return self.t_user_add
        
        