"""
serverless(Lambda)環境用の設定。

値はコードやファイルに置かず、Lambdaの環境変数から組み立てる。
環境変数の実体は Terraform が SSM Parameter Store (SecureString) から注入する。
"""
import json
import os


def _csv_env(name: str) -> list[str]:
    """カンマ区切りの環境変数をリストに変換する（空要素と前後空白は除去）。"""
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_from_env() -> dict:
    """環境変数から既存constantsと同じ形のdictを構築する。必須キー欠落時はKeyError。"""
    return {
        "API_BASE_URL": os.environ["API_BASE_URL"],
        "CLIENT_BASE_URL": os.environ["CLIENT_BASE_URL"],
        "ENCRYPT_SALT": os.environ["ENCRYPT_SALT"],
        "BATCH_ACCESS_KEY": os.environ["BATCH_ACCESS_KEY"],
        "USER_ACCESS_KEY": os.environ["USER_ACCESS_KEY"],
        "ADMIN_ALLOW_IPS": _csv_env("ADMIN_ALLOW_IPS"),
        "DATA_BACKEND": "dynamodb",
        "LOG_ENABLE_FLAGS": json.loads(os.environ.get("LOG_ENABLE_FLAGS", "{}")),
        "CORS_PARAMETERS": {
            "allow_origins": _csv_env("CORS_ALLOW_ORIGINS"),
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        },
    }


# configs/__init__.py の `vars(env_constants)` に合わせてモジュール属性として展開する
# （serverlessモードでのみこのモジュールがimportされるため、他環境には影響しない）
if os.getenv("APP_ENV", "") == "serverless":
    globals().update(load_from_env())
