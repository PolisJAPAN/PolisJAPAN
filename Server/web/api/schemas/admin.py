from typing import Optional

from fastapi import Form
from pydantic import ConfigDict, Field

import api.configs as configs
from api.core.common_schema import ApiError, APIErrorResponses, CommonRequest
from api.models import tables

# ###########################################################################
# admin/info API用スキーマ
# ###########################################################################

# リクエスト
class AdminInfoRequest(CommonRequest):
    """admin/info API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""])
    ):
        return AdminInfoRequest(access_key=access_key)

# レスポンス
class AdminInfoResponse(CommonRequest):
    """admin/info API用レスポンス定義"""
    t_draft_list: list[tables.TDraftModel] = Field(description="テーマ下書き情報")
    model_config = ConfigDict(from_attributes=True)

# APIエラー管理
class AdminInfoErrorResponses(APIErrorResponses):
    """admin/info API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = '管理者権限処理に必要なアクセスキーが不正です。'

    # 固有エラー定義
    class InvalidIPAddressError(ApiError):
        status_code: int = 482
        message: str = 'IPアドレスが不正です。'
        description: str = '許可されたIPアドレスではありません。'

    api_errors = [InvalidAccessKeyError, InvalidIPAddressError]




# ###########################################################################
# admin/approve API用スキーマ
# ###########################################################################

# リクエスト
class AdminApproveRequest(CommonRequest):
    """admin/approve API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    t_draft_id: int = Field(ge=1, le=configs.constants.INT_U_MAX, description="更新対象下書きID")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        t_draft_id: int = Form(..., description="更新対象下書きID", examples=[""])
    ):
        return AdminApproveRequest(access_key=access_key, t_draft_id=t_draft_id)

# レスポンス
class AdminApproveResponse(CommonRequest):
    """admin/approve API用レスポンス定義"""
    t_draft: tables.TDraftModel = Field(description="テーマ下書き情報")

# APIエラー管理
class AdminApproveErrorResponses(APIErrorResponses):
    """admin/approve API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = '管理者権限処理に必要なアクセスキーが不正です。'

    # 固有エラー定義
    class InvalidIPAddressError(ApiError):
        status_code: int = 482
        message: str = 'IPアドレスが不正です。'
        description: str = '許可されたIPアドレスではありません。'

    # 固有エラー定義
    class TDraftNotFoundError(ApiError):
        status_code: int = 483
        message: str = '下書きが存在しません。'
        description: str = '指定された下書きは存在しません。'

    api_errors = [InvalidAccessKeyError, InvalidIPAddressError, TDraftNotFoundError]



# ###########################################################################
# admin/edit API用スキーマ
# ###########################################################################

# リクエスト
class AdminEditRequest(CommonRequest):
    """admin/edit API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    t_draft_id: int = Field(ge=1, description="更新対象下書きID")
    theme_name: Optional[str] = Field(default=None, min_length=1, description="テーマ名")
    theme_description: Optional[str] = Field(default=None, min_length=1, description="テーマ説明")
    theme_comments: Optional[str] = Field(default=None, min_length=1, description="初期コメント")
    theme_category: Optional[int] = Field(default=None, ge=1, description="カテゴリー")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        t_draft_id: int = Form(..., description="更新対象下書きID", examples=[""]),
        theme_name: Optional[str] = Form(default=None, description="テーマ名", examples=[""]),
        theme_description: Optional[str] = Form(default=None, description="テーマ説明", examples=[""]),
        theme_comments: Optional[str] = Form(default=None, description="初期コメント", examples=[""]),
        theme_category: Optional[int] = Form(default=None, description="カテゴリー", examples=[""])
    ):
        return AdminEditRequest(access_key=access_key, t_draft_id=t_draft_id, theme_name=theme_name, theme_description=theme_description, theme_comments=theme_comments, theme_category=theme_category)

# レスポンス
class AdminEditResponse(CommonRequest):
    """admin/edit API用レスポンス定義"""
    t_draft: tables.TDraftModel = Field(description="テーマ下書き情報")

# APIエラー管理
class AdminEditErrorResponses(APIErrorResponses):
    """admin/edit API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = '管理者権限処理に必要なアクセスキーが不正です。'

    # 固有エラー定義
    class InvalidIPAddressError(ApiError):
        status_code: int = 482
        message: str = 'IPアドレスが不正です。'
        description: str = '許可されたIPアドレスではありません。'

    # 固有エラー定義
    class TDraftNotFoundError(ApiError):
        status_code: int = 483
        message: str = '下書きが存在しません。'
        description: str = '指定された下書きは存在しません。'

    api_errors = [InvalidAccessKeyError, InvalidIPAddressError, TDraftNotFoundError]