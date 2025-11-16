import json

from fastapi import Depends, Request
from fastapi.routing import APIRouter

import api.configs as configs
import api.cruds as cruds
import api.models.types as types
import api.schemas.theme as theme_schemas
from api import utils
from api.core.common_route import CommonRoute
from api.core.common_service import error_response
from api.logger import Logger
from api.services.theme import ThemeService

# ルーターに共通ハンドラを設定
router = APIRouter(
    prefix="/theme",
    tags=["theme"],
    route_class=CommonRoute
)


@router.post("/generate_axis", description="テーマ対立軸生成API", responses=error_response(theme_schemas.ThemeGenerateAxisErrorResponses.errors()), response_model=theme_schemas.ThemeGenerateAxisResponse)
async def generate_axis(request: Request, request_body:theme_schemas.ThemeGenerateAxisRequest = Depends(theme_schemas.ThemeGenerateAxisRequest.parse)):
    """
    テーマ対立軸生成API
        テーマ内容から対立軸を生成するAPI
    
    エンドポイント : (base_url)/theme/generate_axis
    
    Args:
        access_key(str) : アクセスキー
        theme(str) : テーマ(ユーザー設定)

    Returns:
        axis(list[str]) : 生成した対立軸

    """

    # 1.サービスの取得
    service : ThemeService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.USER_ACCESS_KEY:
        raise theme_schemas.ThemeGenerateAxisErrorResponses.InvalidAccessKeyError
    
    # WEBを検索して背景情報を収集
    # 背景情報とテーマから、対立軸を生成
    
    result = await service.generate_axis(request_body.theme)

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    return theme_schemas.ThemeGenerateAxisResponse(
        axis=result["axis_list"]
    )


@router.post("/generate_comments", description="テーマコメント生成API", responses=error_response(theme_schemas.ThemeGenerateCommentsErrorResponses.errors()), response_model=theme_schemas.ThemeGenerateCommentsResponse)
async def generate_comments(request: Request, request_body:theme_schemas.ThemeGenerateCommentsRequest = Depends(theme_schemas.ThemeGenerateCommentsRequest.parse)):
    """
    テーマコメント生成API
        テーマ内容、対立軸から初期コメントを生成するAPI
    
    エンドポイント : (base_url)/theme/generate_comments
    
    Args:
        access_key(str) : アクセスキー
        theme(str) : テーマ(ユーザー設定)
        axis(str) : 対立軸(ユーザー設定)

    Returns:
        comments(list[str]) : 生成した意見コメント

    """

    # 1.サービスの取得
    service : ThemeService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.USER_ACCESS_KEY:
        raise theme_schemas.ThemeGenerateCommentsErrorResponses.InvalidAccessKeyError
    
    # テーマ・背景情報・対立軸から、コメントを対立軸ごとに生成
    comments: list[str] = await service.generate_comments_for_axes(request_body.theme, request_body.axis.split(configs.constants.SPLITTER))

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    return theme_schemas.ThemeGenerateCommentsResponse(
        comments=comments
    )

@router.post("/generate_descriptions", description="テーマ説明生成API", responses=error_response(theme_schemas.ThemeGenerateDescriptionsErrorResponses.errors()), response_model=theme_schemas.ThemeGenerateDescriptionsResponse)
async def generate_descriptions(request: Request, request_body:theme_schemas.ThemeGenerateDescriptionsRequest = Depends(theme_schemas.ThemeGenerateDescriptionsRequest.parse)):
    """
    テーマ説明生成API
        テーマ内容、対立軸、コメントからテーマ説明を生成するAPI
    
    エンドポイント : (base_url)/theme/generate_descriptions
    
    Args:
        access_key(str) : アクセスキー
        theme(str) : テーマ(ユーザー設定)
        axis(str) : 対立軸(ユーザー設定)
        comments(str) : コメント(ユーザー設定)

    Returns:
        description(str) : 生成したテーマ説明

    """

    # 1.サービスの取得
    service : ThemeService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.USER_ACCESS_KEY:
        raise theme_schemas.ThemeGenerateCommentsErrorResponses.InvalidAccessKeyError
    
    # テーマ・背景情報・対立軸、コメントから説明の生成を実施
    description : str = await service.generate_description(request_body.theme, request_body.axis.split(configs.constants.SPLITTER), request_body.comments.split(configs.constants.SPLITTER))

    # 3.DB更新処理実行
    try:
        # なし
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    return theme_schemas.ThemeGenerateDescriptionsResponse(
        description=description
    )
    
@router.post("/post_draft", description="テーマ下書き投稿API", responses=error_response(theme_schemas.ThemePostDraftErrorResponses.errors()), response_model=theme_schemas.ThemePostDraftResponse)
async def post_draft(request: Request, request_body:theme_schemas.ThemePostDraftRequest = Depends(theme_schemas.ThemePostDraftRequest.parse)):
    """
    テーマ下書き投稿API
        作成したテーマ下書きを投稿するAPI
    
    エンドポイント : (base_url)/theme/post_draft
    
    Args:
        access_key(str) : アクセスキー
        theme(str) : テーマ(ユーザー設定)
        comments(str) : コメント(ユーザー設定)
        description(str) : 説明(ユーザー設定)
        category(int) : カテゴリ(ユーザー設定)

    Returns:
        is_success(bool) : 投稿処理が成功したかどうか

    """

    # 1.サービスの取得
    service : ThemeService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    # 送信内容をパース

    # 3.DB更新処理実行
    try:
        # 送信された内容を、t_draftの新規レコードとして挿入
        t_draft = await cruds.TDraft.insert(
            db = service.db_session,
            title = "",
            origin_url = "",
            origin_html = "",
            theme_name = request_body.theme,
            theme_description = request_body.description,
            theme_comments = request_body.comments,
            theme_category = request_body.category,
            post_status = types.PostStatus.APPROVED.value,
        )
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return theme_schemas.ThemePostDraftResponse(
        is_success=True
    )