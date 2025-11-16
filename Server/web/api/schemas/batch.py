from typing import Optional

from fastapi import Form
from pydantic import Field

from api.core.common_schema import ApiError, APIErrorResponses, CommonRequest
from api.models import tables

# ###########################################################################
# batch/update API用スキーマ
# ###########################################################################

# リクエスト
class BatchUpdateRequest(CommonRequest):
    """batch/update API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""])
    ):
        return BatchUpdateRequest(access_key=access_key)

# レスポンス
class BatchUpdateResponse(CommonRequest):
    """batch/update API用レスポンス定義"""
    is_success: bool = Field(description="処理が成功したか")

# APIエラー管理
class BatchUpdateErrorResponses(APIErrorResponses):
    """batch/update API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    # 固有エラー定義
    class PolisReportUnavailableError(ApiError):
        status_code: int = 482
        message: str = 'Polisサーバーからの情報取得に失敗しました'
        description: str = 'Polisサーバーからの情報取得に失敗しました。サーバーが停止状態か、接続に問題がある可能性があります。'

    api_errors = [InvalidAccessKeyError, PolisReportUnavailableError]


# ###########################################################################
# batch/create API用スキーマ
# ###########################################################################

# リクエスト
class BatchCreateRequest(CommonRequest):
    """batch/create API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    theme_name: str = Field(min_length=1, max_length=140, description="テーマ名")
    theme_description: str = Field(min_length=1, description="テーマ説明")
    comments: str = Field(min_length=1, description="初期コメント(区切り文字 #####)")
    category: str = Field(min_length=1, description="カテゴリー")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        theme_name: str = Form(..., description="テーマ名", examples=[""]),
        theme_description: str = Form(..., description="テーマ説明", examples=[""]),
        comments: str = Form(..., description="初期コメント(カンマ区切り)", examples=[""]),
        category: str = Form(..., description="カテゴリー", examples=[""])
    ):
        return BatchCreateRequest(access_key=access_key, theme_name=theme_name, theme_description=theme_description, comments=comments, category=category)

# レスポンス
class BatchCreateResponse(CommonRequest):
    """batch/create API用レスポンス定義"""
    is_success: bool = Field(description="処理が成功したか")

# APIエラー管理
class BatchCreateErrorResponses(APIErrorResponses):
    """batch/create API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]
    

# ###########################################################################
# batch/create_all API用スキーマ
# ###########################################################################

# リクエスト
class BatchCreateAllRequest(CommonRequest):
    """batch/create_all API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""])
    ):
        return BatchCreateAllRequest(access_key=access_key)

# レスポンス
class BatchCreateAllResponse(CommonRequest):
    """batch/create_all API用レスポンス定義"""
    is_success: bool = Field(description="処理が成功したか")

# APIエラー管理
class BatchCreateAllErrorResponses(APIErrorResponses):
    """batch/create_all API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]



# ###########################################################################
# batch/generate API用スキーマ
# ###########################################################################

# リクエスト
class BatchGenerateRequest(CommonRequest):
    """batch/generate API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    url: Optional[str] = Field(default=None, description="参照URL")
    html: Optional[str] = Field(default=None, description="参照HTML")
    theme: Optional[str] = Field(default=None, description="テーマ(ユーザー設定)")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        url: Optional[str] = Form(default=None, description="参照URL", examples=[""]),
        html: Optional[str] = Form(default=None, description="参照HTML", examples=[""]),
        theme: Optional[str] = Form(default=None, description="テーマ(ユーザー設定)", examples=[""])
    ):
        return BatchGenerateRequest(access_key=access_key, url=url, html=html, theme=theme)

# レスポンス
class BatchGenerateResponse(CommonRequest):
    """batch/generate API用レスポンス定義"""
    is_success: bool = Field(description="処理が成功したか")

# APIエラー管理
class BatchGenerateErrorResponses(APIErrorResponses):
    """batch/generate API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]
    


# ###########################################################################
# batch/delete API用スキーマ
# ###########################################################################

# リクエスト
class BatchDeleteRequest(CommonRequest):
    """batch/delete API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    t_draft_id: int = Field(ge=1, le=256, description="下書きID")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        t_draft_id: int = Form(..., description="下書きID", examples=[""])
    ):
        return BatchDeleteRequest(access_key=access_key, t_draft_id=t_draft_id)

# レスポンス
class BatchDeleteResponse(CommonRequest):
    """batch/delete API用レスポンス定義"""
    is_success: bool = Field(description="処理が成功したか")

# APIエラー管理
class BatchDeleteErrorResponses(APIErrorResponses):
    """batch/delete API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    # 固有エラー定義
    class ThemeNotFoundError(ApiError):
        status_code: int = 482
        message: str = '対象のテーマが見つかりません。'
        description: str = '指定したテーマは存在していません。'

    # 固有エラー定義
    class DraftNotFoundError(ApiError):
        status_code: int = 483
        message: str = '対象のテーマの下書きが見つかりません。'
        description: str = '指定したテーマは下書きが存在していません。'

    api_errors = [InvalidAccessKeyError, ThemeNotFoundError, DraftNotFoundError]

