from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.core.common_schema import ApiError
from api.routers import user, debug, batch, admin
import api.utils as utils
import api.configs as configs
from api.core.middleware.timeout_middleware import TimeoutMiddleware

# タイムアウト値
REQUEST_TIMEOUT = 300

# FastAPIアプリの構築
app = FastAPI()
app.add_middleware(TimeoutMiddleware, timeout=REQUEST_TIMEOUT)

# 必要なルーターのみinclude、API処理本体はルーター内に記載
# app.include_router(debug.router)
# app.include_router(user.router)
app.include_router(admin.router)
app.include_router(batch.router)

# CORS許可
app.add_middleware(
    CORSMiddleware,
    **configs.constants.CORS_PARAMETERS #環境別のCORS定数を展開
)