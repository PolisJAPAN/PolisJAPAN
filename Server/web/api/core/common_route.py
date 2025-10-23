import traceback
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

import api.configs as configs
import api.configs.user_auth as user_auth
from api import cruds, utils
from api.core.common_schema import ApiError, UnknownError, UserAuthError
from api.core.common_service import get_service
from api.logger import Logger
from api.utils.drivers.database import async_session


class CommonRoute(APIRoute):
    """
    すべてのAPIリクエストに共通する前処理・後処理を定義するルートクラス。

    FastAPIの `APIRoute` を継承し、各エンドポイントの実行前後で共通処理を実行する。
    """
    
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Callable:
            """
            API実行処理本体。FastAPIのルートハンドラーをラップし、共通処理を付与した関数を返す。

            Returns:
                custom_route_handler(Callable): 共通処理付きの非同期ルートハンドラー。
            """
            
            # URIから指定API情報を分解、取得
            api_paths = request.url.path.strip("/").split("/")
            
            # ルーター名、api名を格納
            request.state.router_name = api_paths[0]
            request.state.api_name = api_paths[1]
            
            Logger.info(f"API処理開始 -> ")
            Logger.info(f"  Router : {request.state.router_name}")
            Logger.info(f"  API : {request.state.api_name}")
            
            # 認証チェック（セッションヘッダー取得）
            is_user_auth_api = user_auth.is_user_auth_api(request.state.router_name, request.state.api_name)
            if is_user_auth_api:
                session_id = request.cookies.get("session_id")
                if not session_id:
                    return await self.generate_api_error_response(request, UserAuthError()) 
            
            # DBコネクション開始
            async with async_session() as db:
                # サービス初期化
                request.state.service = await get_service(request.state.router_name)
                request.state.service.db_session = db
                
                # ユーザー認証通信の場合はチェック
                if is_user_auth_api:
                    t_account = await cruds.TAccount.select_by_session_id(request.state.service.db_session, session_id)
                    
                    # アカウントがない場合は、セッション情報が間違っているのでエラー
                    if not t_account:
                        return await self.generate_api_error_response(request, UserAuthError()) 
                    
                    # ログインしたことがないユーザーの場合、先にログインしてセッションを発行しなければユーザー認証通信は使えない
                    if str(t_account.session_id) == "":
                        return await self.generate_api_error_response(request, UserAuthError()) 
                    
                    t_user = await cruds.TUser.select_by_id(request.state.service.db_session, t_account.t_user_id)
                    t_user_add = await cruds.TUserAdd.select_by_t_user_id(request.state.service.db_session, t_account.t_user_id)
                    
                    # アカウント情報があって、他のユーザー関連情報がない場合は不正なデータなので処理終了
                    if not t_user or not t_user_add:
                        return await self.generate_api_error_response(request, UnknownError()) 
                    
                    request.state.service.t_user = t_user
                    request.state.service.t_account = t_account
                    request.state.service.t_user_add = t_user_add

                # 4. API本体へ
                try:
                    response = await original_route_handler(request)
                # 既知のエラーの場合
                except ApiError as err:
                    return await self.generate_api_error_response(request, err)
                # 予期しないエラーの場合
                except Exception as exc:
                    return await self.generate_generic_error_response(request, exc)
            
                Logger.info(f"-> API処理終了")
                await self.finalize_request(request)
                return response

        return custom_route_handler
    
    async def generate_api_error_response(self, request: Request, err: ApiError) -> JSONResponse:
        """
        既知のAPIエラー（ApiError）を補足し、整形済みのJSONレスポンスを返す。

        Args:
            request (Request): FastAPIリクエストオブジェクト。
            err (ApiError): 発生した既知のAPIエラー。

        Returns:
            JSONResponse: エラー情報を含むJSONレスポンス。
        """
        
        # カスタムAPIエラー
        error_time = utils.Time.to_mysql_datetime_str(utils.Time.now())
        trace_id = utils.Error.generate_trace_id()
        
        Logger.info("############################################")
        Logger.info("API処理でエラー発生")
        Logger.info(f"発生API -> {request.url.path}")
        Logger.info(f"エラーコード -> {err.status_code}")
        Logger.info(f"エラーメッセージ -> {err.message}")
        Logger.info(f"発生時刻 -> {error_time}")
        Logger.info(f"trace-id -> {trace_id}")
        Logger.info("############################################")
        
        await self.finalize_request(request)
        
        return JSONResponse(
            status_code=err.status_code,
            content={
                "message": err.message,
                "trace_id": trace_id,
            }
        )
        
    async def generate_generic_error_response(self, request: Request, exc: Exception) -> JSONResponse:
        """
        想定外の例外（Exception）を補足し、標準化されたエラーレスポンスを返す。

        Args:
            request (Request): FastAPIリクエストオブジェクト。
            exc (Exception): 発生した予期しない例外。

        Returns:
            JSONResponse: 500ステータスの汎用エラーレスポンス。
        """
        
        # 一般的な予期せぬエラー
        error_time = utils.Time.to_mysql_datetime_str(utils.Time.now())
        trace_id = utils.Error.generate_trace_id()
        
        Logger.info("############################################")
        Logger.info("API処理で予期せぬエラー発生")
        Logger.info(f"発生API -> {request.url.path}")
        Logger.info(f"例外タイプ -> {type(exc).__name__}")
        Logger.info(f"例外内容 -> {exc}")
        Logger.info(traceback.format_exc())
        Logger.info(f"発生時刻 -> {error_time}")
        Logger.info(f"trace-id -> {trace_id}")
        Logger.info("############################################")
        
        await self.finalize_request(request)
        
        return JSONResponse(
            status_code=500,
            content={
                "message": "サーバー内部で予期しないエラーが発生しました。",
                "trace_id": trace_id,
            }
        )
    
    async def finalize_request(self, request: Request):
        """
        API実行後に共通的に呼び出されるリソース解放処理。

        Args:
            request (Request): FastAPIリクエストオブジェクト。
        """
        
        # S3クライアントのセッションを終了
        await request.state.service.s3.close()
        # DBセッションを終了
        await request.state.service.db_session.close()
        



