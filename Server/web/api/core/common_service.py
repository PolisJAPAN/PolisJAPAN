import importlib
from typing import List, Type

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.common_schema import ApiError
from api.models import tables
from api.utils import StorageS3


class CommonService:
    """
    サービス層の共通機能を提供する基底クラス。

    各APIサービス（例: UserService, AdminService など）はこのクラスを継承し、
    DBセッション・ユーザー情報・S3クライアントなどの共通リソースを共有する。
    """
    
    db_session: AsyncSession
    """非同期DBセッション。FastAPIリクエストごとに確立される。"""

    t_user: tables.TUser
    """ログイン中のユーザー情報（t_userテーブルのレコード）。"""

    t_account: tables.TAccount
    """ユーザーのアカウント情報（t_accountテーブルのレコード）。"""

    t_user_add: tables.TUserAdd
    """ユーザーの追加プロフィール情報（t_user_addテーブルのレコード）。"""

    s3: StorageS3
    """S3ストレージ操作を行うためのユーティリティインスタンス。"""

    
    def __init__(self):
        """
        CommonServiceクラスの初期化処理。

        各サービス共通のリソース準備や前処理を行う。
        """
        
        # 共通の初期化処理など（例：DB接続、設定など）
        pass
    
    async def initialize_utils(self) -> None:
        """
        インスタンス生成が必要なユーティリティクラスを初期化する。

        将来的に他の共通ユーティリティを追加する場合はここに統合する。
        """
        
        # 各ユーティリティをサービスに展開
        self.s3 = StorageS3(bucket="app.pol-is.jp", base_prefix="")
        await self.s3.open()   # 明示的にクライアントを初期化
    
@staticmethod
async def get_service(router_name: str) -> CommonService:
    """
    ルーター名を指定して、対応するサービスクラスのインスタンスを生成する。

    例:
        router_name = "user" → api.services.user.UserService が読み込まれる。

    Args:
        router_name (str): 対応するサービスモジュール名（例: "user", "admin"）。

    Returns:
        CommonService: 対応するサービスクラスのインスタンス。
    """
    
    module_path = f"api.services.{router_name}"
    class_name = f"{router_name.capitalize()}Service"
    
    # パス・クラス名から該当サービスを取得
    module = importlib.import_module(module_path)
    class_entity = getattr(module, class_name)
    instance = class_entity()
    
    # ユーティリティを初期化
    await instance.initialize_utils()

    return instance

@staticmethod
def error_response(error_types: List[Type[ApiError]]) -> dict:
    """
    指定したApiErrorクラス群をOpenAPIのレスポンス定義形式に変換する。

    FastAPIの `responses` パラメータに渡すことで、
    各ステータスコードごとの例外スキーマを自動生成できる。

    Args:
        error_types (List[Type[ApiError]]): 定義済みのApiErrorクラスのリスト。

    Returns:
        dict: OpenAPIレスポンス定義の辞書。
    """
    
    error_dict = {}
    for error_type in error_types:
        if not error_dict.get(error_type.status_code):
            error_dict[error_type.status_code] = {
                'description': f'<b>{error_type.message}</b><br> {error_type.description}',
                'content': {
                    'application/json': {
                        'example': {
                            'detail': error_type.message
                        }
                    }
                }}
    return error_dict