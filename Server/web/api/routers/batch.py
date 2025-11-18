import json
import os

from fastapi import Depends, Request
from fastapi.routing import APIRouter

import api.configs as configs
import api.cruds as cruds
import api.models.types as types
import api.schemas.batch as batch_schemas
from api import utils
from api.core.common_route import CommonRoute
from api.core.common_service import error_response
from api.logger import Logger
from api.services.batch import BatchService

# ルーターに共通ハンドラを設定
router = APIRouter(
    prefix="/batch",
    tags=["batch"],
    route_class=CommonRoute
)

THEME_HEADERS = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date"]
"""テーマ記録用CSVのカラム一覧"""

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

    # 管理しているテーマ一覧のCSVをS3から取得する
    themes_str, themes_list = await service.get_theme_csv()
    
    # 更新するデータのみのリスト
    update_themes = []
    update_comment_csv = {}
    
    # 各テーマ用のデータを取得
    for theme in themes_list:
        
        # Polisから集計CSVを取得
        report_id = theme["report_id"]
        report_csv_str, comments = await service.get_report_csv(report_id)
        
        # コメント数、投票数を集計
        total_comments = 0
        total_votes = 0
        for comment in comments:
            total_votes += int(comment["total-votes"])
            total_comments = total_comments + 1
        
        Logger.debug(f"{theme['title']} before {theme['votes']} -> after {total_votes}  (Refresh -> {int(theme['votes']) != int(total_votes)})")
        
        # 現在S3に保存済みの集計CSVと比較
        if (int(theme['votes']) != int(total_votes)):
            # 変更があった場合は、取得したファイルを設置用に配列に格納
            update_row = theme.copy()
            update_row["votes"] = str(total_votes)
            update_row["comments"] = str(total_comments)
            update_themes.append(update_row)
            
            # S3にアップするリストにCSVを追加
            update_comment_csv[theme["conversation_id"]] = report_csv_str
    
    # 取得内容をテーマ一覧CSVに反映
    result_themes = utils.Common.merge_lists(themes_list, update_themes)
    
    # 最終出力テーマ一覧
    themes_headers = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date"]
    fixed_theme_csv_text = utils.CSV.to_csv(result_themes, themes_headers)

    try:
        if update_comment_csv and len(update_comment_csv.items()) > 0:
            Logger.debug("S3に更新を実施")
            
            # 変更があった集計CSVをS3に格納
            for conversation_id, report_csv_str in update_comment_csv.items():
                await service.s3.upload_bytes(f"csv/report/report_{conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv")
            
            # テーマ一覧CSVを更新
            await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
            
            # キャッシュクリア
            await service.s3.clear_cache(os.environ["CLOUDFRONT_DISTRIBUTION"],["/csv/*"])
    except Exception as e:
        raise e
    
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
    
    # 承認済テーマ一覧を取得
    t_draft_list = await cruds.TDraft.select_by_post_status(service.db_session, types.PostStatus.APPROVED.value)
    Logger.debug(json.dumps([t_draft.theme_name for t_draft in t_draft_list], indent=4, ensure_ascii=False))
    
    # テーマ一覧を取得
    themes_str, theme_list = await service.get_theme_csv()
    
    # 承認済テーマを一括作成
    report_csv_list = []
    for t_draft in t_draft_list:
        # コメントリストを文字列にパース
        comments = t_draft.theme_comments.split(configs.constants.SPLITTER)
        
        # テーマを作成
        report_csv_str, theme_info = await service.create_theme(theme_list, str(t_draft.theme_name), str(t_draft.theme_description), comments, str(t_draft.theme_category))
        
        # テーマ一覧に追加
        theme_list.append(theme_info)
        report_csv_list.append(report_csv_str)
        
        t_draft.conversation_id = theme_info["conversation_id"]
        t_draft.report_id = theme_info["report_id"]
        
    # テーマ一覧CSVをS3にアップ
    fixed_theme_csv_text = utils.CSV.to_csv(theme_list, THEME_HEADERS)
    await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
    
    # レポートから取得したファイルをS3に一括アップ
    for report_csv_str in report_csv_list:
        await service.s3.upload_bytes(f"csv/report/report_{theme_info['conversation_id']}.csv", report_csv_str.encode("utf-8"), content_type="text/csv")
        
    await service.s3.clear_cache(os.environ["CLOUDFRONT_DISTRIBUTION"],["/csv/*"])

    # 3.DB更新処理実行
    try:
        for t_draft in t_draft_list:
            await cruds.TDraft.update_post_info(service.db_session, t_draft, t_draft.conversation_id, t_draft.report_id,types.PostStatus.POSTED.value)
            
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

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
    t_draft = await cruds.TDraft.select_by_id(service.db_session, request_body.t_draft_id)
    
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
        await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
        
    # レポートファイルがある場合は削除
    is_report_exists = await service.s3.exists(f"/csv/report/report_{t_draft.conversation_id}.csv")
    if is_report_exists:
        await service.s3.delete_object(f"csv/report/report_{t_draft.conversation_id}.csv")
    
    # キャッシュクリア
    await service.s3.clear_cache(os.environ["CLOUDFRONT_DISTRIBUTION"],["/csv/*"])

    # 3.DB更新処理実行
    try:
        # 対象下書き情報を論理削除
        if t_draft:
            await cruds.TDraft.delete_by_id(service.db_session, t_draft.id)
        
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchDeleteResponse(
        is_success=True
    )