import os

from api.models.types import LogLevel


def _csv_env(name: str, default: str) -> list[str]:
    """カンマ区切りの環境変数をリストに変換する（空要素と前後空白は除去）。"""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


API_BASE_URL = "http://localhost:80"
"""APIベースURL"""

CLIENT_BASE_URL = "http://localhost:3000"
"""フロントエンドURL"""

ENCRYPT_SALT = os.environ.get("ENCRYPT_SALT", "local-dev-salt")
"""暗号化ソルト値（実値は Server/web/.env で設定）"""

BATCH_ACCESS_KEY = os.environ.get("BATCH_ACCESS_KEY", "local-dev-batch-key")
"""バッチ処理アクセスキー（実値は Server/web/.env で設定）"""

USER_ACCESS_KEY = os.environ.get("USER_ACCESS_KEY", "local-dev-user-key")
"""ユーザー処理アクセスキー（実値は Server/web/.env で設定）"""

ADMIN_ALLOW_IPS = _csv_env("ADMIN_ALLOW_IPS", "127.0.0.1,172.16.0.0/12")
"""許可IP一覧（カンマ区切りの環境変数で設定）"""

LOG_ENABLE_FLAGS = {
    LogLevel.DEBUG: True,
    LogLevel.DEBUG_FOCUSED: True,
    LogLevel.INFO: True,
    LogLevel.WARNING: True,
    LogLevel.ERROR: True,
    LogLevel.CRITICAL: True,
}
"""ログ レベル別の有効フラグ"""

CORS_PARAMETERS = {
    "allow_origins" : ["*"],
    "allow_credentials" : True, # セッションIDセット用
    "allow_methods" : ["*"],
    "allow_headers" : ["*"]
}
"""環境別のCORS設定"""
