from fastapi import Depends, Request
from fastapi.routing import APIRouter

import api.configs as configs
import api.cruds as cruds
import api.models.types as types
import api.schemas.admin as admin_schemas
from api import utils
from api.core.common_route import CommonRoute
from api.core.common_service import error_response
from api.logger import Logger
from api.services.admin import AdminService

# ルーターに共通ハンドラを設定
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    route_class=CommonRoute
)

@router.post("/info", description="情報取得API", responses=error_response(admin_schemas.AdminInfoErrorResponses.errors()), response_model=admin_schemas.AdminInfoResponse)
async def info(request: Request, request_body:admin_schemas.AdminInfoRequest = Depends(admin_schemas.AdminInfoRequest.parse)):
    """
    情報取得API
        管理者画面で表示する各種情報を取得するAPI
    
    エンドポイント : (base_url)/admin/info
    
    Args:
        access_key(str) : アクセスキー

    Returns:
        t_draft_list(list[tables.tDraftModel]) : テーマ下書き情報

    """

    # 1.サービスの取得
    service : AdminService = request.state.service

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise admin_schemas.AdminInfoErrorResponses.InvalidAccessKeyError
    
    # IPアドレスが許可リストになければエラー
    Logger.debug(request.client.host)
    if not utils.Security.is_allowed_ip(request.client.host, configs.constants.ADMIN_ALLOW_IPS):
        raise admin_schemas.AdminInfoErrorResponses.InvalidIPAddressError
    
    # DBから有効な下書き情報一覧を取得
    t_draft_list = await cruds.TDraft.select_all(service.db_session)

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    # 下書き情報一覧を返却
    return admin_schemas.AdminInfoResponse(
        t_draft_list=t_draft_list
    )



@router.post("/approve", description="テーマ情報承認API", responses=error_response(admin_schemas.AdminApproveErrorResponses.errors()), response_model=admin_schemas.AdminApproveResponse)
async def approve(request: Request, request_body:admin_schemas.AdminApproveRequest = Depends(admin_schemas.AdminApproveRequest.parse)):
    """
    テーマ情報承認API
        生成済のテーマ情報に対する承認をデータに反映するAPI
    
    エンドポイント : (base_url)/admin/approve
    
    Args:
        access_key(str) : アクセスキー
        t_draft_id(int) : 更新対象下書きID

    Returns:
        t_draft(tables.tDraftModel) : テーマ下書き情報

    """

    # 1.サービスの取得
    service : AdminService = request.state.service

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise admin_schemas.AdminApproveErrorResponses.InvalidAccessKeyError
    # IPアドレスが許可リストになければエラー
    if not utils.Security.is_allowed_ip(request.client.host, configs.constants.ADMIN_ALLOW_IPS):
        raise admin_schemas.AdminApproveErrorResponses.InvalidIPAddressError
    
    # DBから対象の下書き情報を取得
    t_draft = await cruds.TDraft.select_by_id(service.db_session, request_body.t_draft_id)
    
    # 対象の下書きが存在しなければエラー
    if not t_draft:
        raise admin_schemas.AdminApproveErrorResponses.TDraftNotFoundError

    # 3.DB更新処理実行
    try:
        # 下書きのステータスを承認状態に更新
        t_draft = await cruds.TDraft.update_post_status(service.db_session, t_draft, types.PostStatus.APPROVED.value)
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # 更新済下書き情報を返却

    return admin_schemas.AdminApproveResponse(
        t_draft=t_draft
    )



@router.post("/edit", description="テーマ情報更新API", responses=error_response(admin_schemas.AdminEditErrorResponses.errors()), response_model=admin_schemas.AdminEditResponse)
async def edit(request: Request, request_body:admin_schemas.AdminEditRequest = Depends(admin_schemas.AdminEditRequest.parse)):
    """
    テーマ情報更新API
        生成済のテーマ情報の内容修正を実施するAPI
    
    エンドポイント : (base_url)/admin/edit
    
    Args:
        access_key(str) : アクセスキー
        t_draft_id(int) : 更新対象下書きID
        theme_name(str) : テーマ名
        theme_description(str) : テーマ説明
        theme_comments(str) : 初期コメント
        theme_category(int) : カテゴリー

    Returns:
        t_draft(tables.tDraftModel) : テーマ下書き情報

    """

    # 1.サービスの取得
    service : AdminService = request.state.service

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise admin_schemas.AdminEditErrorResponses.InvalidAccessKeyError
    
    # IPアドレスが許可リストになければエラー
    if not utils.Security.is_allowed_ip(request.client.host, configs.constants.ADMIN_ALLOW_IPS):
        raise admin_schemas.AdminEditErrorResponses.InvalidIPAddressError
    
    # DBから対象の下書き情報を取得
    t_draft = await cruds.TDraft.select_by_id(service.db_session, request_body.t_draft_id)
    
    # 対象の下書きが存在しなければエラー
    if not t_draft:
        raise admin_schemas.AdminApproveErrorResponses.TDraftNotFoundError

    # 3.DB更新処理実行
    try:
        # 下書きのデータを更新
        t_draft = await cruds.TDraft.update_content(service.db_session, t_draft, request_body.theme_name, request_body.theme_description, request_body.theme_comments, request_body.theme_category)
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # 更新済下書き情報を返却
    return admin_schemas.AdminEditResponse(
        t_draft=t_draft
    )
