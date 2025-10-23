from datetime import datetime

from fastapi import Depends, Request, Response
from fastapi.routing import APIRouter

import api.cruds as cruds
import api.schemas.user as user_schemas
from api import utils
from api.core.common_route import CommonRoute
from api.core.common_service import error_response
from api.services.user import UserService

# ルーターに共通ハンドラを設定
router = APIRouter(
    prefix="/user",
    tags=["user"],
    route_class=CommonRoute
)

@router.post("/mail_check", description="メールアドレスチェックAPI", responses=error_response(user_schemas.UserMailCheckErrorResponses.errors()), response_model=user_schemas.UserMailCheckResponse)
async def mail_check(request: Request, request_body:user_schemas.UserMailCheckRequest = Depends(user_schemas.UserMailCheckRequest.parse)):
    """
    メールアドレスチェックAPI
        送信したメールアドレスに紐付くアカウントが存在しないかどうかをチェックする
    
    エンドポイント : (base_url)/user/mail_check
    
    Args:
        mail(str) : メールアドレス

    Returns:
        is_valid_address(bool) : 有効なメールアドレスか

    """
    
    # 1.サービスの取得
    service: UserService = request.state.service

    # 2.DB更新前の事前処理
    # メールアドレスでt_accountを取得
    duplicate_t_account = await cruds.TAccount.select_by_mail(service.db_session, request_body.mail)
    # アカウントが存在する場合、戻り値に反映
    is_valid_address: bool = bool(duplicate_t_account == None)

    # 3.DB更新処理実行
        # なし

    # 4.レスポンスの作成と返却
    return user_schemas.UserMailCheckResponse(
        is_valid_address=is_valid_address
    )


@router.post("/create", description="ユーザー登録API", responses=error_response(user_schemas.UserCreateErrorResponses.errors()), response_model=user_schemas.UserCreateResponse)
async def create(request: Request, request_body:user_schemas.UserCreateRequest = Depends(user_schemas.UserCreateRequest.parse)):
    """
    ユーザー作成API
        新規ユーザーとその関連情報を作成するAPI。ユーザー登録時に使用する
    
    エンドポイント : (base_url)/user/create
    
    Args:
        name(str) : ユーザー名
        mail(str) : メールアドレス
        password(str) : パスワード

    Returns:
        is_success(bool) : ユーザー作成に成功したか

    """
    
    # 1.サービスの取得
    service: UserService = request.state.service
    
    # 2.DB更新前の事前処理
    
    # メールアドレスが重複するアカウントが存在するかチェック
    duplicate_t_account = await cruds.TAccount.select_by_mail(service.db_session, request_body.mail)
    
    if duplicate_t_account:
        raise user_schemas.UserCreateErrorResponses.UserAlreadyExistError
    
    # パスワードをハッシュ化して保存
    hased_password = utils.Security.hash_password(request_body.password)
    
    # 3.DB更新処理実行
    try:
        t_user = await cruds.TUser.insert(service.db_session, request_body.name, "")
        t_account = await cruds.TAccount.insert(service.db_session, t_user.id, request_body.mail, hased_password)
        t_user_add = await cruds.TUserAdd.insert(service.db_session, t_user.id)
        
        # 全データ更新後、更新を確定
        await service.db_session.commit()
    except Exception as e:
        # 途中でエラーが発生した場合、ロールバック
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    return user_schemas.UserCreateResponse(
        is_success = True
    )


@router.post("/login", description="ログインAPI", responses=error_response(user_schemas.UserLoginErrorResponses.errors()), response_model=user_schemas.UserLoginResponse)
async def login(response: Response, request: Request, request_body:user_schemas.UserLoginRequest = Depends(user_schemas.UserLoginRequest.parse)):
    """
    ログインAPI
        ログイン処理を行うAPI。
    
    エンドポイント : (base_url)/user/login
    
    Args:
        mail(str) : メールアドレス
        password(str) : パスワード

    Returns:
        t_user(tables.TUserModel) : ユーザー情報
        t_user_add(tables.TUserAddModel) : ユーザー付随情報

    """
    
    # 1.サービスの取得
    service: UserService = request.state.service

    # 2.DB更新前の事前処理
    # リクエストされたメールアドレスのユーザーが存在するかチェック
    t_account = await cruds.TAccount.select_by_mail(service.db_session, request_body.mail)
    t_user = await cruds.TUser.select_by_id(service.db_session, t_account.t_user_id)
    t_user_add = await cruds.TUserAdd.select_by_t_user_id(service.db_session, t_account.t_user_id)
    
    # メールアドレスに紐づくユーザーが存在しない場合、エラー
    if not t_account:
        raise user_schemas.UserLoginErrorResponses.InvalidLoginError
    
    # パスワードが合致しない場合、エラー
    if not utils.Security.verify_password(request_body.password, t_account.password):
        raise user_schemas.UserLoginErrorResponses.InvalidLoginError
    
    # 現在時刻を取得
    now : datetime = utils.Time.now()
    
    # 新規セッションIDを取得
    new_session_id: str = await service.generate_unique_session_id(service.db_session)
    
    # 3.DB更新処理実行
    try:
        # t_userの最終ログイン日時を更新
        t_user = await cruds.TUser.update_last_login_date(service.db_session, t_user, now)
        # t_accountのセッションidを更新
        t_account = await cruds.TAccount.update_session_id(service.db_session, t_account, new_session_id)
        # t_userの最終ログイン日時を更新
        t_account = await cruds.TAccount.update_last_api_date(service.db_session, t_account, now)
        
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却

    response.set_cookie(
        key="session_id",
        value=new_session_id,
        httponly=True,      # JavaScriptから読めない
        secure=True,        # HTTPSのみ
        samesite="lax"      # CSRF対策
    )

    return user_schemas.UserLoginResponse(
        t_user=t_user,
        t_user_add=t_user_add
    )
    
@router.post("/reload", description="ユーザー情報再取得API", responses=error_response(user_schemas.UserReloadErrorResponses.errors()), response_model=user_schemas.UserReloadResponse)
async def reload(request: Request, request_body:user_schemas.UserReloadRequest = Depends(user_schemas.UserReloadRequest.parse)):
    """
    ユーザー情報再取得API
        リロード等を行った際の情報再取得処理を行うAPI。
    
    エンドポイント : (base_url)/user/reload
    
    Args:

    Returns:
        t_user(tables.TUserModel) : ユーザー情報
        t_user_add(tables.TUserAddModel) : ユーザー付随情報

    """
    
    # 1.サービスの取得
    service: UserService = request.state.service

    # 2.DB更新前の事前処理
    # なし

    # 3.DB更新処理実行
    # なし

    # 4.レスポンスの作成と返却
    return user_schemas.UserReloadResponse(
        t_user=service.t_user,
        t_user_add=service.t_user_add
    )


@router.post("/edit", description="ユーザー情報更新API", responses=error_response(user_schemas.UserEditErrorResponses.errors()), response_model=user_schemas.UserEditResponse)
async def edit(request: Request, request_body:user_schemas.UserEditRequest = Depends(user_schemas.UserEditRequest.parse)):
    """
    ユーザー情報更新API
        ユーザーの基本情報の処理を行うAPI。
    
    エンドポイント : (base_url)/user/edit
    
    Args:
        name(str) : ユーザー名
        profile(str) : ユーザープロフィール
        user_prompt(str) : ユーザープロンプト

    Returns:
        t_user(tables.TUserModel) : ユーザー情報
        t_user_add(tables.TUserAddModel) : ユーザー付随情報

    """
    
    # 1.サービスの取得
    service: UserService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    
    # テーブルごとの更新データを作成
    # t_userの更新データを作成
    t_user_edit_data = service.get_t_user_edit_data(name = request_body.name, profile = request_body.profile)
    # t_user_addの更新データを作成
    t_user_add_edit_data = service.get_t_user_add_edit_data(user_prompt = request_body.user_prompt)

    # 3.DB更新処理実行
    try:
        # t_userの更新情報がある場合
        updated_t_user = service.t_user
        if t_user_edit_data:
        # 更新内容を渡してt_userを更新
            updated_t_user = await cruds.TUser.update(service.db_session, service.t_user, t_user_edit_data)
            
        # t_user_addの更新情報がある場合
        updated_t_user_add = service.t_user_add
        if t_user_add_edit_data:
            # 更新内容を渡してt_user_addを更新
            updated_t_user_add = await cruds.TUserAdd.update(service.db_session, service.t_user_add, t_user_add_edit_data)
            
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    return user_schemas.UserEditResponse(
        t_user=updated_t_user,
        t_user_add=updated_t_user_add
    )

@router.post("/delete", description="ユーザー退会API", responses=error_response(user_schemas.UserDeleteErrorResponses.errors()), response_model=user_schemas.UserDeleteResponse)
async def delete(request: Request, request_body:user_schemas.UserDeleteRequest = Depends(user_schemas.UserDeleteRequest.parse)):
    """
    ユーザー退会API
        ユーザー情報を論理削除し、退会を行うAPI。
    
    エンドポイント : (base_url)/user/delete
    
    Args:
        password(str) : パスワード

    Returns:
        is_success(bool) : 削除に成功したか

    """

    
    # 1.サービスの取得
    service: UserService = request.state.service

    # なし

    # 2.DB更新前の事前処理
    # 入力されたパスワードとの合致チェックを行う
    if not utils.Security.verify_password(request_body.password, service.t_account.password):
        # 合致しない場合、エラー
        raise user_schemas.UserDeleteErrorResponses.PasswordUnmatchError

    # 3.DB更新処理実行
    try:
        # ユーザー削除時のデータ削除処理を行う
        # t_userを論理削除
        await cruds.TUser.delete_by_id(service.db_session, service.t_user.id)
        
        # t_accountを論理削除
        await cruds.TAccount.delete_by_id(service.db_session, service.t_account.id)
        
        # t_user_addを論理削除
        await cruds.TUserAdd.delete_by_id(service.db_session, service.t_user_add.id)
        
        await service.db_session.commit()
    except Exception as e:
        await service.db_session.rollback()
        raise e

    # 4.レスポンスの作成と返却
    # 削除成功したかどうかを返却値に含める
    return user_schemas.UserDeleteResponse(
        is_success=True
    )
    