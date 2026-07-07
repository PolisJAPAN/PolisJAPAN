import os

from fastapi import Depends, Request
from fastapi.routing import APIRouter

import api.configs as configs
import api.schemas.batch as batch_schemas
from api import utils
from api.core.common_route import CommonRoute
from api.core.common_service import error_response
from api.services.batch import CSV_CACHE_CONTROL, THEME_HEADERS, BatchService

# ルーターに共通ハンドラを設定
router = APIRouter(
    prefix="/batch",
    tags=["batch"],
    route_class=CommonRoute
)

@router.post("/update", description="テーマ情報更新API", responses=error_response(batch_schemas.BatchUpdateErrorResponses.errors()), response_model=batch_schemas.BatchUpdateResponse)
async def update(request: Request, request_body:batch_schemas.BatchUpdateRequest = Depends(batch_schemas.BatchUpdateRequest.parse)):
    """
    テーマ情報更新API
        各テーマの最新情報を取得し、データを更新する
    
    エンドポイント : (base_url)/batch/update
    
    Args:
        access_key(str) : アクセスキー

    Returns:
        is_success(bool) : 処理が成功したか

    """
    
    # 1.サービスの取得
    service : BatchService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise batch_schemas.BatchUpdateErrorResponses.InvalidAccessKeyError

    # 全テーマの投票情報を更新
    await service.update_themes()

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchUpdateResponse(
        is_success=True
    )

@router.post("/create_all", description="テーマ一括作成API", responses=error_response(batch_schemas.BatchCreateAllErrorResponses.errors()), response_model=batch_schemas.BatchCreateAllResponse)
async def create_all(request: Request, request_body:batch_schemas.BatchCreateAllRequest = Depends(batch_schemas.BatchCreateAllRequest.parse)):
    """
    テーマ一括作成API
        登録された承認済テーマ情報からPolis経由でテーマを作成し、記録するAPI
    
    エンドポイント : (base_url)/batch/create_all
    
    Args:
        access_key(str) : アクセスキー

    Returns:
        is_success(bool) : 処理が成功したか

    """
    
    # 1.サービスの取得
    service : BatchService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise batch_schemas.BatchCreateAllErrorResponses.InvalidAccessKeyError
    
    # 承認済テーマを一括作成（HTTP経由は現行cron互換のため全件処理）
    await service.publish_approved_drafts()

    # 3.DB更新処理実行
    # なし（publish_approved_drafts内でストアへの反映まで実施）

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchCreateAllResponse(
        is_success=True
    )

@router.post("/delete", description="テーマ削除API", responses=error_response(batch_schemas.BatchDeleteErrorResponses.errors()), response_model=batch_schemas.BatchDeleteResponse)
async def delete(request: Request, request_body:batch_schemas.BatchDeleteRequest = Depends(batch_schemas.BatchDeleteRequest.parse)):
    """
    テーマ削除API
        指定したテーマを削除する管理用API
    
    エンドポイント : (base_url)/batch/delete
    
    Args:
        access_key(str) : アクセスキー
        conversation_id(str) : 会話ID

    Returns:
        is_success(bool) : 処理が成功したか

    """

    # 1.サービスの取得
    service : BatchService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise batch_schemas.BatchDeleteErrorResponses.InvalidAccessKeyError
    
    # 会話IDから下書きを取得
    t_draft = await service.draft_store.select_by_id(request_body.t_draft_id)
    
    if not t_draft:
        raise batch_schemas.BatchDeleteErrorResponses.ThemeNotFoundError
    
    # CSVを読み込み
    themes_str, theme_list = await service.get_theme_csv()
    
    # 会話IDからCSV上でのIDを特定
    target_theme = next((theme for theme in theme_list if theme["conversation_id"] == t_draft.conversation_id), None)
    
    if target_theme:
        # CSVからデータを削除する
        filtered_theme_list = [theme for theme in theme_list if theme and theme.get("conversation_id") != t_draft.conversation_id]
    
        # S3に再アップロード
        fixed_theme_csv_text = utils.CSV.to_csv(filtered_theme_list, THEME_HEADERS)
        await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)

    # レポートファイルがある場合は削除
    is_report_exists = await service.s3.exists(f"/csv/report/report_{t_draft.conversation_id}.csv")
    if is_report_exists:
        await service.s3.delete_object(f"csv/report/report_{t_draft.conversation_id}.csv")

    # 削除はCache-Control(TTL)では反映できない（削除済みオブジェクトはヘッダを持たない）ため、
    # 対象パスのみピンポイントでキャッシュ無効化する。低頻度の管理操作のためコストはほぼゼロ
    distribution_id = os.environ.get("CLOUDFRONT_DISTRIBUTION", "")
    if distribution_id:
        await service.s3.create_invalidation(distribution_id, [f"/csv/report/report_{t_draft.conversation_id}.csv", "/csv/themes.csv"])

    # 3.DB更新処理実行
    try:
        # 対象下書き情報を論理削除
        if t_draft:
            await service.draft_store.delete_by_id(t_draft.id)

        await service.draft_store.commit()
    except Exception as e:
        await service.draft_store.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchDeleteResponse(
        is_success=True
    )

@router.get("/healthcheck", description="ヘルスチェックAPI", responses=error_response(batch_schemas.BatchHealthcheckErrorResponses.errors()), response_model=batch_schemas.BatchHealthcheckResponse)
async def healthcheck(request: Request, request_body:batch_schemas.BatchHealthcheckRequest = Depends(batch_schemas.BatchHealthcheckRequest.parse)):
    """
    ヘルスチェックAPI
        WEBサーバーのヘルス状態をチェックするAPI
    
    エンドポイント : (base_url)/batch/healthcheck
    
    Args:


    Returns:
        is_success(bool) : 成功情報

    """

    # 1.サービスの取得
    service : BatchService = request.state.service

    # なし

    # 2.DB更新前の事前処理

    # なし

    # 3.DB更新処理実行

    # なし

    # 4.レスポンスの作成と返却

    return batch_schemas.BatchHealthcheckResponse(
        is_success=True
    )
