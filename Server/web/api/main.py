import os
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from api.core.common_schema import ApiError
from api.routers import batch, admin, theme
import api.utils as utils
import api.configs as configs
from api.core.middleware.timeout_middleware import TimeoutMiddleware

# タイムアウト値
REQUEST_TIMEOUT = 300

# Swagger(/docs, /redoc, /openapi.json)を公開しない環境。
# 本番LambdaはAPP_ENV=serverlessで動くため、productionだけを見ると本番で公開されてしまう
DOCS_DISABLED_ENVS = ("production", "serverless")


def create_app(app_env: str) -> FastAPI:
    """環境に応じてSwaggerの公開有無を切り替えたFastAPIアプリを作る。"""
    if app_env in DOCS_DISABLED_ENVS:
        return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    return FastAPI()


# FastAPIアプリの構築
APP_ENV = os.getenv("APP_ENV", "production")
app = create_app(APP_ENV)

app.add_middleware(TimeoutMiddleware, timeout=REQUEST_TIMEOUT)

# 必要なルーターのみinclude、API処理本体はルーター内に記載
app.include_router(admin.router)
app.include_router(batch.router)
app.include_router(theme.router)

# CORS許可
app.add_middleware(
    CORSMiddleware,
    **configs.constants.CORS_PARAMETERS #環境別のCORS定数を展開
)

# Lambda用エントリポイント（API Gateway経由の起動時に使用）
# uvicorn起動（Docker/EC2/ローカル）とは共存し、既存の動作には影響しない
handler = Mangum(app, lifespan="off")