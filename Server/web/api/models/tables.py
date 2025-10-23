from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT

from api.utils.drivers.database import Base


class TUser(Base):
    """
        ユーザー情報を管理するテーブル。ユーザーの存在と他ユーザーに公開できる情報のみを管理する。
    """

    __tablename__ = "t_user"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, comment="ID")
    name = Column(String(128), nullable=False, comment="ユーザー名")
    profile = Column(String(256), nullable=False, comment="ユーザープロフィール")
    last_login_date = Column(DateTime, comment="最終ログイン日時")
    status = Column(Integer, nullable=False, default=1, comment="ステータス")
    create_date = Column(DateTime, nullable=False, comment="作成日時")
    update_date = Column(DateTime, nullable=False, comment="更新日時")

class TUserModel(BaseModel):
    """
        (Pydanticモデル) ユーザー情報を管理するテーブル。ユーザーの存在と他ユーザーに公開できる情報のみを管理する。
    """
    
    id: int
    name: str
    profile: str
    last_login_date: datetime
    status: int
    create_date: datetime
    update_date: datetime

    model_config = ConfigDict(from_attributes=True)



class TAccount(Base):
    """
        ユーザーアカウント情報を管理するテーブル。ユーザーの認証に使用する情報のみを格納する。他ユーザーには公開しない。
    """
    
    __tablename__ = "t_account"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, comment="ID")
    t_user_id = Column(Integer, nullable=False, comment="ユーザーID")
    mail = Column(String(256), nullable=False, comment="メールアドレス")
    password = Column(String(256), nullable=False, comment="パスワード")
    session_id = Column(String(64), nullable=False, comment="セッションID")
    last_api_date = Column(DateTime, comment="最終API実行日時")
    status = Column(Integer, nullable=False, default=1, comment="ステータス")
    create_date = Column(DateTime, nullable=False, comment="作成日時")
    update_date = Column(DateTime, nullable=False, comment="更新日時")

class TAccountModel(BaseModel):
    """
        (Pydanticモデル) ユーザーアカウント情報を管理するテーブル。ユーザーの認証に使用する情報のみを格納する。他ユーザーには公開しない。
    """
    
    id: int
    t_user_id: int
    mail: str
    password: str
    session_id: str
    last_api_date: datetime
    status: int
    create_date: datetime
    update_date: datetime

    model_config = ConfigDict(from_attributes=True)



class TUserAdd(Base):
    """
        ユーザー付随情報を管理するテーブル。ユーザー自身からのみ参照される情報を格納する。他ユーザーには公開しない。
    """
    
    __tablename__ = "t_user_add"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, comment="ID")
    t_user_id = Column(Integer, nullable=False, comment="ユーザーID")
    user_prompt = Column(Text, nullable=False, comment="ユーザープロンプト")
    status = Column(Integer, nullable=False, default=1, comment="ステータス")
    create_date = Column(DateTime, nullable=False, comment="作成日時")
    update_date = Column(DateTime, nullable=False, comment="更新日時")

class TUserAddModel(BaseModel):
    """
        (Pydanticモデル) ユーザー付随情報を管理するテーブル。ユーザー自身からのみ参照される情報を格納する。他ユーザーには公開しない。
    """
    
    id: int
    t_user_id: int
    user_prompt: str
    status: int
    create_date: datetime
    update_date: datetime

    model_config = ConfigDict(from_attributes=True)


class TDraft(Base):
    """
        テーマ下書き情報を管理するテーブル。情報収集で集めたテーマ候補を保存する
    """
    __tablename__ = "t_draft"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, comment="ID")
    title = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="タイトル")
    origin_url = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="参照URL")
    origin_html = Column(LONGTEXT(collation="utf8mb4_unicode_ci"), nullable=False, comment="参照HTML")
    theme_name = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="テーマ名")
    theme_description = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="テーマ説明")
    theme_comments = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="初期コメント")
    theme_category = Column(Integer, nullable=False, default=0, comment="カテゴリー")
    conversation_id = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="Polis管理ID")
    report_id = Column(Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="Polisレポート管理ID")
    post_status = Column(Integer, nullable=False, default=0, comment="投稿ステータス")
    status = Column(Integer, nullable=False, default=1, comment="ステータス")
    create_date = Column(DateTime, nullable=False, comment="作成日時")
    update_date = Column(DateTime, nullable=False, comment="更新日時")

class TDraftModel(BaseModel):
    """
        (Pydanticモデル) テーマ下書き情報を管理するテーブル。情報収集で集めたテーマ候補を保存する
    """
    id: int
    title: str
    origin_url: str
    origin_html: str = Field(exclude=True)
    theme_name: str
    theme_description: str
    theme_comments: str
    theme_category: int
    conversation_id: str
    report_id: str
    post_status: int
    status: int
    create_date: datetime
    update_date: datetime

    model_config = ConfigDict(from_attributes=True)





