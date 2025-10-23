import importlib
import os
import types

# 環境変数を読み込み
APP_ENV = os.getenv("APP_ENV", "development")

from . import constants as base_constants

# 環境別の変数を読み込み
if APP_ENV == "production":
    from .production import constants as env_constants
    from .production import credentials as credentials
    from .production import database as database
    from .production import cache as cache

elif APP_ENV == "development":
    from .development import constants as env_constants
    from .development import credentials as credentials
    from .development import database as database
    from .development import cache as cache

elif APP_ENV == "localhost":
    from .localhost import constants as env_constants
    from .localhost import credentials as credentials
    from .localhost import database as database
    from .localhost import cache as cache

else:
    raise ValueError("存在しない環境が指定されています")

# 環境別constantsの展開処理
# ネームスペースにマージ
merged_constants = {}
merged_constants.update(vars(base_constants))
if env_constants:
    merged_constants.update(vars(env_constants))

# SimpleNamespaceとしてconfig.constantsにバインド
constants = types.SimpleNamespace(**{
    k: v for k, v in merged_constants.items()
    if not k.startswith("__")
})

# 環境変数に設定を行う
for key, value in credentials.ENVBIRONMENT_VALIABLES.items():
    os.environ[key] = value