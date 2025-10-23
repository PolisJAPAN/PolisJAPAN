from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from api.configs import database

# 宣言的ベース
Base = declarative_base()

# DB URL
ASYNC_DB_URL = (
    f"mysql+aiomysql://{database.DB_USER}:{database.DB_PASSWORD}"
    f"@{database.DB_HOST}:{database.DB_PORT}/{database.DB_NAME}?charset=utf8mb4"
)

# エンジン作成
async_engine = create_async_engine(ASYNC_DB_URL, echo=True,
    connect_args={
        "charset": "utf8mb4",
        "use_unicode": True,
        "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    }
)

# async_sessionmakerでセッションファクトリを生成（SQLAlchemy 2.0以降推奨）
async_session = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
)
