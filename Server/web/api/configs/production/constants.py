from api.models.types import LogLevel

API_BASE_URL = "http://api.example.com/"
"""APIベースURL"""

CLIENT_BASE_URL = "http://app.example.com/"
"""フロントエンドURL"""

ENCRYPT_SALT = "EXAMPLE_SALT_VALUE"
"""暗号化ソルト値"""

BATCH_ACCESS_KEY = "EXAMPLE_ACCESS_KEY"
"""バッチ処理アクセスキー"""

ADMIN_ALLOW_IPS = [
    "172.16.0.0/12", #　Dockerプライベートネットワーク
    "127.0.0.1" #　ローカルホスト
]
"""許可IP一覧"""

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
    "allow_origins" : [CLIENT_BASE_URL, API_BASE_URL],
    "allow_origins" : ["*"],
    "allow_credentials" : True, # セッションIDセット用
    "allow_methods" : ["*"],
    "allow_headers" : ["*"]
}
"""環境別のCORS設定"""