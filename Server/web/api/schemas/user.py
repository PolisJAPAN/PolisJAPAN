from typing import Optional

from fastapi import Form
from pydantic import Field

from api.core.common_schema import ApiError, APIErrorResponses, CommonRequest
from api.models import tables

# ###########################################################################
# user/mail_check API用スキーマ
# ###########################################################################

# リクエスト
class UserMailCheckRequest(CommonRequest):
    """user/mail_check API用リクエスト定義"""
    mail: str = Field(min_length=1, max_length=256, description="メールアドレス")

    @classmethod
    def parse(
        cls,
        mail: str = Form(..., description="メールアドレス", examples=[""])
    ):
        return UserMailCheckRequest(mail=mail)

# レスポンス
class UserMailCheckResponse(CommonRequest):
    """user/mail_check API用レスポンス定義"""
    is_valid_address: bool = Field(description="有効なメールアドレスか")

# APIエラー管理
class UserMailCheckErrorResponses(APIErrorResponses):
    """user/mail_check API用エラー管理クラス"""

    # 固有エラー定義
        # 固有エラーなし

    api_errors = []


# ###########################################################################
# user/create API用スキーマ
# ###########################################################################

# リクエスト
class UserCreateRequest(CommonRequest):
    """user/create API用リクエスト定義"""
    name: str = Field(min_length=1, max_length=128, description="ユーザー名")
    mail: str = Field(min_length=1, max_length=256, description="メールアドレス")
    password: str = Field(min_length=1, max_length=256, description="パスワード")

    @classmethod
    def parse(
        cls,
        name: str = Form(..., description="ユーザー名", examples=[""]),
        mail: str = Form(..., description="メールアドレス", examples=[""]),
        password: str = Form(..., description="パスワード", examples=[""])
    ):
        return UserCreateRequest(name=name, mail=mail, password=password)

# レスポンス
class UserCreateResponse(CommonRequest):
    """user/create API用レスポンス定義"""
    is_success: bool = Field(description="ユーザー作成に成功したか")

# APIエラー管理
class UserCreateErrorResponses(APIErrorResponses):
    """user/create API用エラー管理クラス"""

    # 固有エラー定義
    class UserAlreadyExistError(ApiError):
        status_code: int = 481
        message: str = 'メールアドレスが既に登録されています。'
        description: str = 'ユーザー登録しようとしたメールアドレスが既に登録済みであることを意味します'

    api_errors = [UserAlreadyExistError]
    

# ###########################################################################
# user/login API用スキーマ
# ###########################################################################

# リクエスト
class UserLoginRequest(CommonRequest):
    """user/login API用リクエスト定義"""
    mail: str = Field(min_length=1, max_length=256, description="メールアドレス")
    password: str = Field(min_length=1, max_length=256, description="パスワード")

    @classmethod
    def parse(
        cls,
        mail: str = Form(..., description="メールアドレス", examples=[""]),
        password: str = Form(..., description="パスワード", examples=[""])
    ):
        return UserLoginRequest(mail=mail, password=password)

# レスポンス
class UserLoginResponse(CommonRequest):
    """user/login API用レスポンス定義"""
    t_user: tables.TUserModel = Field(description="ユーザー情報")
    t_user_add: tables.TUserAddModel = Field(description="ユーザー付随情報")

# APIエラー管理
class UserLoginErrorResponses(APIErrorResponses):
    """user/login API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidLoginError(ApiError):
        status_code: int = 481
        message: str = 'メールアドレスとパスワードが合致しません。'
        description: str = 'ログインしようとしたユーザーのメールアドレスが存在しない、またはパスワードが合致しないことを意味します。'

    api_errors = [InvalidLoginError]

    
# ###########################################################################
# user/reload API用スキーマ
# ###########################################################################

# リクエスト
class UserReloadRequest(CommonRequest):
    """user/reload API用リクエスト定義"""

    @classmethod
    def parse(cls):
        return UserReloadRequest()

# レスポンス
class UserReloadResponse(CommonRequest):
    """user/reload API用レスポンス定義"""
    t_user: tables.TUserModel = Field(description="ユーザー情報")
    t_user_add: tables.TUserAddModel = Field(description="ユーザー付随情報")

# APIエラー管理
class UserReloadErrorResponses(APIErrorResponses):
    """user/reload API用エラー管理クラス"""

    # 固有エラー定義
        # 固有エラーなし

    api_errors = []



# ###########################################################################
# user/edit API用スキーマ
# ###########################################################################

# リクエスト
class UserEditRequest(CommonRequest):
    """user/edit API用リクエスト定義"""
    name: Optional[str] = Field(default=None, max_length=128, description="ユーザー名")
    profile: Optional[str] = Field(default=None, max_length=256, description="ユーザープロフィール")
    user_prompt: Optional[str] = Field(default=None, description="ユーザープロンプト")

    @classmethod
    def parse(
        cls,
        name: Optional[str] = Form(default=None, description="ユーザー名", examples=[""]),
        profile: Optional[str] = Form(default=None, description="ユーザープロフィール", examples=[""]),
        user_prompt: Optional[str] = Form(default=None, description="ユーザープロンプト", examples=[""])
    ):
        return UserEditRequest(name=name, profile=profile, user_prompt=user_prompt)

# レスポンス
class UserEditResponse(CommonRequest):
    """user/edit API用レスポンス定義"""
    t_user: tables.TUserModel = Field(description="ユーザー情報")
    t_user_add: tables.TUserAddModel = Field(description="ユーザー付随情報")

# APIエラー管理
class UserEditErrorResponses(APIErrorResponses):
    """user/edit API用エラー管理クラス"""

    # 固有エラー定義
        # 固有エラーなし

    api_errors = []
    
    
# ###########################################################################
# user/delete API用スキーマ
# ###########################################################################

# リクエスト
class UserDeleteRequest(CommonRequest):
    """user/delete API用リクエスト定義"""
    password: str = Field(max_length=128, description="パスワード")

    @classmethod
    def parse(
        cls,
        password: str = Form(..., description="パスワード", examples=[""])
    ):
        return UserDeleteRequest(password=password)

# レスポンス
class UserDeleteResponse(CommonRequest):
    """user/delete API用レスポンス定義"""
    is_success: bool = Field(description="削除に成功したか")

# APIエラー管理
class UserDeleteErrorResponses(APIErrorResponses):
    """user/delete API用エラー管理クラス"""

    # 固有エラー定義
    class PasswordUnmatchError(ApiError):
        status_code: int = 481
        message: str = '入力されたパスワードが合致しません。'
        description: str = '削除確認のために送信されたパスワードがユーザーの設定パスワードと合致しなかったことを示します。'

    api_errors = [PasswordUnmatchError]