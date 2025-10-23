import json

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
            
        # 現在S3に保存済みの集計CSVと比較
        if theme["votes"] != total_votes:
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

    # 3.DB更新処理実行
    try:
        # 変更があった集計CSVをS3に格納
        for conversation_id, report_csv_str in update_comment_csv.items():
            await service.s3.upload_bytes(f"csv/report/report_{conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv")
        
        # テーマ一覧CSVを更新
        await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
    except Exception as e:
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchUpdateResponse(
        is_success=True
    )

@router.post("/create", description="テーマ作成API", responses=error_response(batch_schemas.BatchCreateErrorResponses.errors()), response_model=batch_schemas.BatchCreateResponse)
async def create(request: Request, request_body:batch_schemas.BatchCreateRequest = Depends(batch_schemas.BatchCreateRequest.parse)):
    """
    テーマ作成API
        Polis経由でテーマを作成し、記録するAPI
    
    エンドポイント : (base_url)/batch/create
    
    Args:
        access_key(str) : アクセスキー
        theme_name(str) : テーマ名
        theme_description(str) : テーマ説明
        comments(str) : 初期コメント(区切り文字 #####)
        category(str) : カテゴリー

    Returns:
        is_success(bool) : 処理が成功したか

    """
    
    # 1.サービスの取得
    service : BatchService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise batch_schemas.BatchCreateErrorResponses.InvalidAccessKeyError
    
    comments = request_body.comments.split("#####")
    
    # テーマ一覧を取得
    themes_str, theme_list = await service.get_theme_csv()
    
    # テーマを作成
    report_csv_str, theme_info = await service.create_theme(theme_list, request_body.theme_name, request_body.theme_description, comments, request_body.category)
    
    # テーマ一覧に追加
    theme_list.append(theme_info)
    
    # テーマ一覧CSVをS3にアップ
    fixed_theme_csv_text = utils.CSV.to_csv(theme_list, THEME_HEADERS)
    await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
    
    # レポートから取得したファイルをS3にアップ
    await service.s3.upload_bytes(f"csv/report/report_{theme_info['conversation_id']}.csv", report_csv_str.encode("utf-8"), content_type="text/csv")

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchCreateResponse(
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
    Logger.debug(t_draft_list)
    
    # テーマ一覧を取得
    themes_str, theme_list = await service.get_theme_csv()
    
    # 承認済テーマを一括作成
    report_csv_list = []
    for t_draft in t_draft_list:
        # コメントリストを配列にパース
        comments = t_draft.theme_comments.split("#####")
        
        # テーマを作成
        report_csv_str, theme_info = await service.create_theme(theme_list, str(t_draft.theme_name), str(t_draft.theme_description), comments, str(t_draft.theme_category))
        
        # テーマ一覧に追加
        theme_list.append(theme_info)
        report_csv_list.append(report_csv_str)
        
    # テーマ一覧CSVをS3にアップ
    fixed_theme_csv_text = utils.CSV.to_csv(theme_list, THEME_HEADERS)
    await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv")
    
    # レポートから取得したファイルをS3に一括アップ
    for report_csv_str in report_csv_list:
        await service.s3.upload_bytes(f"csv/report/report_{theme_info['conversation_id']}.csv", report_csv_str.encode("utf-8"), content_type="text/csv")

    # 3.DB更新処理実行
    try:
        await cruds.TDraft.update_list_post_status(service.db_session, t_draft_list, types.PostStatus.POSTED.value)
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchCreateAllResponse(
        is_success=True
    )
    
@router.post("/generate", description="テーマ内容生成API", responses=error_response(batch_schemas.BatchGenerateErrorResponses.errors()), response_model=batch_schemas.BatchGenerateResponse)
async def generate(request: Request, request_body:batch_schemas.BatchGenerateRequest = Depends(batch_schemas.BatchGenerateRequest.parse)):
    """
    テーマ内容生成API
        特定話題からテーマ内容を生成するAPI
    
    エンドポイント : (base_url)/batch/generate
    
    Args:
        access_key(str) : アクセスキー
        url(str) : 参照URL
        html(str) : 参照HTML

    Returns:
        is_success(bool) : 処理が成功したか

    """
    # 1.サービスの取得
    service : BatchService = request.state.service
    
    # なし

    # 2.DB更新前の事前処理
    # アクセスキーがサーバーに設置された値と一致しなければエラー
    if request_body.access_key != configs.constants.BATCH_ACCESS_KEY:
        raise batch_schemas.BatchGenerateErrorResponses.InvalidAccessKeyError
    
    page_title : str = ""
    main_tweet : dict = {}
    reaction_tweet_list : list[dict] = []
    background_detail : str = ""
    
    # urlから話題情報と反応を取得
    if request_body.url:
        page_title, main_tweet, reaction_tweet_list, background_detail = await service.get_info_from_toggetter(request_body.url)
    elif request_body.html:
        page_title, main_tweet, reaction_tweet_list, background_detail = await service.get_info_from_twitter(request_body.html)
    
    # テーマを生成
    theme_result = await service.generate_theme(page_title, main_tweet, reaction_tweet_list, background_detail)
    Logger.debug_focused(json.dumps(theme_result, indent=4, ensure_ascii=False)) 

    # 3.DB更新処理実行
    try:
        t_draft = await cruds.TDraft.insert(
            db = service.db_session,
            title = page_title,
            origin_url = str(request_body.url),
            origin_html = str(request_body.html),
            theme_name = theme_result["theme"],
            theme_description = theme_result["description"],
            theme_comments = theme_result["comments_str"],
            theme_category = theme_result["category"],
        )
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # なし

    return batch_schemas.BatchGenerateResponse(
        is_success=True
    )