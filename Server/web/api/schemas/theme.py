from typing import Optional

from fastapi import Form
from pydantic import Field

from api.core.common_schema import ApiError, APIErrorResponses, CommonRequest
from api.models import tables

# ###########################################################################
# theme/generate_axis API用スキーマ
# ###########################################################################

# リクエスト
class ThemeGenerateAxisRequest(CommonRequest):
    """theme/generate_axis API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    theme: str = Field(description="テーマ(ユーザー設定)")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        theme: str = Form(..., description="テーマ(ユーザー設定)", examples=[""])
    ):
        return ThemeGenerateAxisRequest(access_key=access_key, theme=theme)

# レスポンス
class ThemeGenerateAxisResponse(CommonRequest):
    """theme/generate_axis API用レスポンス定義"""
    axis: list[str] = Field(description="生成した対立軸")

# APIエラー管理
class ThemeGenerateAxisErrorResponses(APIErrorResponses):
    """theme/generate_axis API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]
    


# ###########################################################################
# theme/generate_comments API用スキーマ
# ###########################################################################

# リクエスト
class ThemeGenerateCommentsRequest(CommonRequest):
    """theme/generate_comments API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    theme: str = Field(description="テーマ(ユーザー設定)")
    axis: str = Field(description="対立軸(ユーザー設定)")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        theme: str = Form(..., description="テーマ(ユーザー設定)", examples=[""]),
        axis: str = Form(..., description="対立軸(ユーザー設定)", examples=[""])
    ):
        return ThemeGenerateCommentsRequest(access_key=access_key, theme=theme, axis=axis)

# レスポンス
class ThemeGenerateCommentsResponse(CommonRequest):
    """theme/generate_comments API用レスポンス定義"""
    comments: list[str] = Field(description="生成した意見コメント")

# APIエラー管理
class ThemeGenerateCommentsErrorResponses(APIErrorResponses):
    """theme/generate_comments API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]
    

# ###########################################################################
# theme/generate_descriptions API用スキーマ
# ###########################################################################

# リクエスト
class ThemeGenerateDescriptionsRequest(CommonRequest):
    """theme/generate_descriptions API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    theme: str = Field(description="テーマ(ユーザー設定)")
    axis: str = Field(description="対立軸(ユーザー設定)")
    comments: str = Field(description="コメント(ユーザー設定)")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        theme: str = Form(..., description="テーマ(ユーザー設定)", examples=[""]),
        axis: str = Form(..., description="対立軸(ユーザー設定)", examples=[""]),
        comments: str = Form(..., description="コメント(ユーザー設定)", examples=[""])
    ):
        return ThemeGenerateDescriptionsRequest(access_key=access_key, theme=theme, axis=axis, comments=comments)

# レスポンス
class ThemeGenerateDescriptionsResponse(CommonRequest):
    """theme/generate_descriptions API用レスポンス定義"""
    description: str = Field(description="生成したテーマ説明")

# APIエラー管理
class ThemeGenerateDescriptionsErrorResponses(APIErrorResponses):
    """theme/generate_descriptions API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]

# ###########################################################################
# theme/post_draft API用スキーマ
# ###########################################################################

# リクエスト
class ThemePostDraftRequest(CommonRequest):
    """theme/post_draft API用リクエスト定義"""
    access_key: str = Field(min_length=1, max_length=256, description="アクセスキー")
    theme: str = Field(description="テーマ(ユーザー設定)")
    comments: str = Field(description="コメント(ユーザー設定)")
    description: str = Field(description="説明(ユーザー設定)")
    category: int = Field(description="カテゴリ(ユーザー設定)")

    @classmethod
    def parse(
        cls,
        access_key: str = Form(..., description="アクセスキー", examples=[""]),
        theme: str = Form(..., description="テーマ(ユーザー設定)", examples=[""]),
        comments: str = Form(..., description="コメント(ユーザー設定)", examples=[""]),
        description: str = Form(..., description="説明(ユーザー設定)", examples=[""]),
        category: int = Form(..., description="カテゴリ(ユーザー設定)", examples=[""])
    ):
        return ThemePostDraftRequest(access_key=access_key, theme=theme, comments=comments, description=description, category=category)

# レスポンス
class ThemePostDraftResponse(CommonRequest):
    """theme/post_draft API用レスポンス定義"""
    is_success: bool = Field(description="投稿処理が成功したかどうか")

# APIエラー管理
class ThemePostDraftErrorResponses(APIErrorResponses):
    """theme/post_draft API用エラー管理クラス"""

    # 固有エラー定義
    class InvalidAccessKeyError(ApiError):
        status_code: int = 481
        message: str = 'アクセスキーが不正です'
        description: str = 'バッチ実行に必要なアクセスキーが不正です。'

    api_errors = [InvalidAccessKeyError]




