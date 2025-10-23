from pydantic import BaseModel

class CommonRequest(BaseModel):
    pass

class CommonResponse(BaseModel):
    pass


class ApiError(Exception):
    """ APIエラーの基底となるクラス """
    status_code: int = 400
    message: str = 'APIでエラーが発生しました。'
    description: str =  'APIでエラーが発生しました。'

class UnknownError(ApiError):
    """ エラー定義：不明なエラー """
    status_code: int = 461
    message: str = '不明なエラーが発生しました。'
    description: str =  'ハンドリングされていないエラーの発生を意味します。'

class UserAuthError(ApiError):
    """ エラー定義：ユーザー認証エラー """
    status_code: int = 462
    message: str = 'ユーザーが認証されていません。'
    description: str =  'ユーザー認証が必要なAPIにおいて、セッションID(sid)による認証が失敗したことを意味します。'


class APIErrorResponses:
    """ APIごとのエラー群定義の基底となるクラス """
    # システム上の汎用エラーはここに列挙する
    common_errors: list = [
        UnknownError,
        UserAuthError
    ]
    
    # API個別のエラーはここに定義する
    api_errors: list = []
    
    @classmethod
    def errors(cls) -> list:
        """
        共通エラーとAPI個別エラーを結合して返す。

        必要に応じて、`set` による重複排除などを行うことも可能。

        Returns:
            list: 共通エラーと個別エラーを統合したリスト。
        """
        
        # 必要なら set などで重複排除も可
        return cls.common_errors + cls.api_errors
    

