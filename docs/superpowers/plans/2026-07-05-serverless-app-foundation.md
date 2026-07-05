# サーバーレス対応・基盤編 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPIアプリをLambda実行可能にする基盤（テスト基盤・Cache-Control化・Mangumハンドラ・環境変数ベース設定・memcached削除）を、現行のEC2/Docker動作を壊さずに整える。

**Architecture:** 既存のFastAPIコードは温存し、(1) S3アップロード時にCache-Controlヘッダを付与してCloudFront無効化を廃止、(2) Mangumアダプタで同一アプリをLambdaハンドラ化、(3) `APP_ENV=serverless` 時のみ環境変数から設定を組み立てる configs サブモジュールを追加する。DynamoDB移行とバッチのLambda分割は後続プラン（DynamoDB移行編・バッチLambda化編）で行う。

**Tech Stack:** Python 3.11 / FastAPI / Poetry / pytest + pytest-asyncio / Mangum / aioboto3

**前提・注意:**
- 作業ディレクトリ: `Server/web/`。テスト実行はホストの python3.11+ でも Docker コンテナ内でも可（`poetry install` 済みであること）。
- **コミットは feature ブランチ `feature/serverless-migration` 上で行う**（mainに未コミット変更が多数あるため、ブランチ作成時は `git switch -c` で現在の作業ツリーを持ち越してよい。コミット対象は本プランで触るファイルのみを `git add <path>` で明示指定し、無関係な未コミット変更を巻き込まないこと）。
- `configs/localhost/` 等の環境設定ファイルはシークレットを含む。**テストコードや計画にこれらの値を書かない**こと。テストは `APP_ENV=localhost` で既存ファイルを読み込むだけにする。

---

## File Structure

```
Server/web/
├── pyproject.toml                     # 変更: dev依存追加(pytest等)、mangum追加、python-memcached削除
├── api/
│   ├── main.py                        # 変更: Mangum handler追加
│   ├── configs/
│   │   ├── __init__.py                # 変更: serverless分岐追加、cache import削除
│   │   └── serverless/                # 新規: 環境変数から設定を組み立てるモジュール
│   │       ├── __init__.py
│   │       ├── constants.py
│   │       ├── credentials.py
│   │       └── database.py
│   ├── routers/batch.py               # 変更: clear_cache呼び出し削除、cache_control付与
│   └── utils/storage_s3.py            # 変更: build_put_args分離 + cache_control対応、clear_cache削除
└── tests/                             # 新規
    ├── __init__.py
    ├── conftest.py
    ├── test_storage_s3.py
    ├── test_main_handler.py
    └── test_configs_serverless.py
```

---

### Task 1: pytest基盤の導入

**Files:**
- Modify: `Server/web/pyproject.toml`
- Create: `Server/web/tests/__init__.py`
- Create: `Server/web/tests/conftest.py`

- [ ] **Step 1: ブランチ作成**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
git switch -c feature/serverless-migration
```

- [ ] **Step 2: dev依存を追加**

`Server/web/pyproject.toml` の `[build-system]` セクションの**直前**に以下を追加:

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.3"
pytest-asyncio = "^0.24"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: テストディレクトリを作成**

`Server/web/tests/__init__.py` — 空ファイルを作成。

`Server/web/tests/conftest.py`:

```python
import os
import sys

# api パッケージを import 可能にする（tests/ は Server/web/ 直下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# configs は import 時に APP_ENV で分岐するため、テストでは localhost を使う
os.environ.setdefault("APP_ENV", "localhost")
```

- [ ] **Step 4: 依存を解決してpytestが動くことを確認**

```bash
cd Server/web && poetry lock && poetry install --with dev && poetry run pytest --collect-only -q
```

Expected: `no tests ran`（エラーなく終了すること）

- [ ] **Step 5: Commit**

```bash
git add Server/web/pyproject.toml Server/web/poetry.lock Server/web/tests/__init__.py Server/web/tests/conftest.py
git commit -m "test: pytest基盤を導入（サーバーレス移行 基盤編 Task1）"
```

---

### Task 2: CSVアップロードのCache-Control化とCloudFront無効化の廃止

コスト分析（docs/インフラ棚卸しとサーバーレス移行計画.md §3）で特定した月$27のCloudFront無効化を廃止し、`Cache-Control: max-age=300` によるTTL方式に置き換える。クライアントは `cache: 'no-store'` でfetchするためブラウザキャッシュへの影響はない（2026-07-04 実測確認済み）。

**Files:**
- Modify: `Server/web/api/utils/storage_s3.py`
- Modify: `Server/web/api/routers/batch.py`
- Test: `Server/web/tests/test_storage_s3.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_storage_s3.py`:

```python
from api.utils.storage_s3 import build_put_args


def test_build_put_args_minimal():
    args = build_put_args(bucket="b", key="k", data=b"x")
    assert args == {"Bucket": "b", "Key": "k", "Body": b"x"}


def test_build_put_args_with_content_type_and_cache_control():
    args = build_put_args(
        bucket="app.pol-is.jp",
        key="csv/themes.csv",
        data=b"data",
        content_type="text/csv",
        cache_control="max-age=300",
    )
    assert args["ContentType"] == "text/csv"
    assert args["CacheControl"] == "max-age=300"


def test_build_put_args_extra_overrides():
    args = build_put_args(bucket="b", key="k", data=b"x", extra_put_args={"Metadata": {"a": "1"}})
    assert args["Metadata"] == {"a": "1"}
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd Server/web && poetry run pytest tests/test_storage_s3.py -v
```

Expected: FAIL — `ImportError: cannot import name 'build_put_args'`

- [ ] **Step 3: build_put_args を実装し upload_bytes を書き換える**

`Server/web/api/utils/storage_s3.py` — import群の直後（`class StorageS3Error` の前）に追加:

```python
def build_put_args(
    *,
    bucket: str,
    key: str,
    data: bytes,
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
    extra_put_args: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """put_object に渡す引数dictを構築する（純関数・テスト用に分離）。"""
    put_args: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": data}
    if content_type:
        put_args["ContentType"] = content_type
    if cache_control:
        put_args["CacheControl"] = cache_control
    if extra_put_args:
        put_args.update(extra_put_args)
    return put_args
```

同ファイルの `upload_bytes` メソッド全体を以下に置き換え（シグネチャに `cache_control` 追加、引数構築を `build_put_args` に委譲）:

```python
    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: Optional[str] = None,
        cache_control: Optional[str] = None,
        extra_put_args: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """
        指定キーにバイト列データをアップロードする。

        Args:
            key (str): アップロード先のオブジェクトキー（prefixを除いた相対パス）。
            data (bytes): アップロードするデータ。
            content_type (Optional[str]): Content-Type ヘッダ（例: "text/plain"）。
            cache_control (Optional[str]): Cache-Control ヘッダ（例: "max-age=300"）。
                CloudFrontはこの値をTTLとして尊重するため、キャッシュ無効化APIの代わりに使う。
            extra_put_args (Optional[Mapping[str, Any]]): put_object に渡す追加パラメータ。

        Raises:
            StorageS3Error: S3通信エラーや認証エラーなど。
        """
        put_args = build_put_args(
            bucket=self.bucket,
            key=self._full_key(key),
            data=data,
            content_type=content_type,
            cache_control=cache_control,
            extra_put_args=extra_put_args,
        )
        try:
            await self._exist_client().put_object(**put_args)
        except (BotoCoreError, ClientError) as e:
            raise StorageS3Error(f"upload_bytes failed: {e}") from e
```

同ファイル末尾の `clear_cache` メソッド（250〜273行）を**丸ごと削除**する。あわせて先頭の `import time` と `from typing import ... Sequence` の `Sequence` を削除する（他に使用箇所がないため）。

- [ ] **Step 4: テストが通ることを確認**

```bash
cd Server/web && poetry run pytest tests/test_storage_s3.py -v
```

Expected: PASS（3件）

- [ ] **Step 5: routers/batch.py から無効化を排除しCache-Controlを付与**

`Server/web/api/routers/batch.py` — CSV_CACHE_CONTROL 定数を追加し、3つのエンドポイントを修正する。

`THEME_HEADERS` 定義の直後に追加:

```python
CSV_CACHE_CONTROL = "max-age=300"
"""CSV配信のCloudFront TTL。無効化APIの代わりにオブジェクト側のヘッダで鮮度を制御する"""
```

`update` 内（94〜108行の try ブロック）を以下に置き換え:

```python
    try:
        if update_comment_csv and len(update_comment_csv.items()) > 0:
            Logger.debug("S3に更新を実施")
            
            # 変更があった集計CSVをS3に格納
            for conversation_id, report_csv_str in update_comment_csv.items():
                await service.s3.upload_bytes(f"csv/report/report_{conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)
            
            # テーマ一覧CSVを更新
            await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)
    except Exception as e:
        raise e
```

`create_all` 内（169〜177行）を以下に置き換え（`clear_cache` 行を削除し `cache_control` を付与。**既存バグ修正を含む**: report_csv のキーがループ外の `theme_info` を参照していたため、`zip` で t_draft と対応づける）:

```python
    # テーマ一覧CSVをS3にアップ
    fixed_theme_csv_text = utils.CSV.to_csv(theme_list, THEME_HEADERS)
    await service.s3.upload_bytes(f"csv/themes.csv", fixed_theme_csv_text.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)
    
    # レポートから取得したファイルをS3に一括アップ
    for t_draft, report_csv_str in zip(t_draft_list, report_csv_list):
        await service.s3.upload_bytes(f"csv/report/report_{t_draft.conversation_id}.csv", report_csv_str.encode("utf-8"), content_type="text/csv", cache_control=CSV_CACHE_CONTROL)
```

`delete` 内: 241行の `upload_bytes` 呼び出しに `, cache_control=CSV_CACHE_CONTROL` を追加し、248〜249行の

```python
    # キャッシュクリア
    await service.s3.clear_cache(os.environ["CLOUDFRONT_DISTRIBUTION"],["/csv/*"])
```

を削除する。ファイル先頭の `import os` は `os.environ` の使用がなくなるため削除する。

- [ ] **Step 6: 参照が残っていないことを確認**

```bash
cd Server/web && grep -rn "clear_cache\|CLOUDFRONT_DISTRIBUTION" api --include="*.py" | grep -v configs/
```

Expected: 出力なし（configs内のcredentials定義のみ残るのは許容）

```bash
cd Server/web && poetry run pytest -v && poetry run python -c "import api.utils.storage_s3; print('import OK')"
```

Expected: 全テストPASS + `import OK`

- [ ] **Step 7: Commit**

```bash
git add Server/web/api/utils/storage_s3.py Server/web/api/routers/batch.py Server/web/tests/test_storage_s3.py
git commit -m "feat: CSV配信をCache-Control(TTL300s)方式に変更、CloudFront無効化を廃止"
```

---

### Task 3: Mangumハンドラの追加

**Files:**
- Modify: `Server/web/pyproject.toml`（mangum追加）
- Modify: `Server/web/api/main.py`
- Test: `Server/web/tests/test_main_handler.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_main_handler.py`:

```python
def test_handler_is_mangum_adapter():
    from mangum import Mangum

    from api.main import app, handler

    assert isinstance(handler, Mangum)
    # ラップ対象が同一のFastAPIアプリであること
    assert handler.app is app


def test_app_has_expected_routes():
    from api.main import app

    paths = {route.path for route in app.routes}
    assert "/batch/healthcheck" in paths
    assert "/theme/post_draft" in paths
    assert "/admin/info" in paths
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd Server/web && poetry run pytest tests/test_main_handler.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mangum'`

- [ ] **Step 3: mangumを依存に追加**

```bash
cd Server/web && poetry add "mangum@^0.19"
```

- [ ] **Step 4: main.py にハンドラを追加**

`Server/web/api/main.py` — import群に `from mangum import Mangum` を追加し、ファイル末尾（CORS設定の後）に追加:

```python
# Lambda用エントリポイント（API Gateway経由の起動時に使用）
# uvicorn起動（Docker/EC2/ローカル）とは共存し、既存の動作には影響しない
handler = Mangum(app, lifespan="off")
```

- [ ] **Step 5: テストが通ることを確認**

```bash
cd Server/web && poetry run pytest tests/test_main_handler.py -v
```

Expected: PASS（2件）

- [ ] **Step 6: 既存のDocker起動が壊れていないことを確認（回帰）**

```bash
cd Server && docker-compose build web && docker-compose up -d && sleep 10 && curl -s http://localhost:80/batch/healthcheck && docker-compose down
```

Expected: `{"is_success":true}`

- [ ] **Step 7: Commit**

```bash
git add Server/web/pyproject.toml Server/web/poetry.lock Server/web/api/main.py Server/web/tests/test_main_handler.py
git commit -m "feat: Mangumハンドラを追加しLambda起動に対応"
```

---

### Task 4: serverless設定モードの追加（環境変数ベースのconfigs）

Lambda環境ではファイルではなく環境変数（Terraformが SSM Parameter Store から注入）から設定を組み立てる。`APP_ENV=serverless` の新分岐を追加する。既存3環境の動作は変えない。

**Files:**
- Create: `Server/web/api/configs/serverless/__init__.py`（空）
- Create: `Server/web/api/configs/serverless/constants.py`
- Create: `Server/web/api/configs/serverless/credentials.py`
- Create: `Server/web/api/configs/serverless/database.py`
- Modify: `Server/web/api/configs/__init__.py`
- Test: `Server/web/tests/test_configs_serverless.py`

- [ ] **Step 1: 失敗するテストを書く**

`Server/web/tests/test_configs_serverless.py`:

```python
import os

import pytest


@pytest.fixture
def serverless_env(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.pol-is.jp/")
    monkeypatch.setenv("CLIENT_BASE_URL", "https://app.pol-is.jp/")
    monkeypatch.setenv("ENCRYPT_SALT", "test-salt")
    monkeypatch.setenv("BATCH_ACCESS_KEY", "test-batch-key")
    monkeypatch.setenv("USER_ACCESS_KEY", "test-user-key")
    monkeypatch.setenv("ADMIN_ALLOW_IPS", "203.0.113.1/32, 198.51.100.0/24")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.pol-is.jp,https://pol-is.jp")


def test_load_constants_from_env(serverless_env):
    from api.configs.serverless.constants import load_from_env

    c = load_from_env()
    assert c["API_BASE_URL"] == "https://api.pol-is.jp/"
    assert c["BATCH_ACCESS_KEY"] == "test-batch-key"
    # カンマ区切り文字列 → リスト（空白は除去）
    assert c["ADMIN_ALLOW_IPS"] == ["203.0.113.1/32", "198.51.100.0/24"]
    # CORS_PARAMETERS は CORSMiddleware(**params) 互換の形
    assert c["CORS_PARAMETERS"]["allow_origins"] == ["https://app.pol-is.jp", "https://pol-is.jp"]
    assert c["CORS_PARAMETERS"]["allow_credentials"] is True
    assert c["CORS_PARAMETERS"]["allow_methods"] == ["*"]
    assert c["CORS_PARAMETERS"]["allow_headers"] == ["*"]


def test_load_constants_missing_required_raises(monkeypatch):
    monkeypatch.delenv("BATCH_ACCESS_KEY", raising=False)
    from api.configs.serverless.constants import load_from_env

    with pytest.raises(KeyError):
        load_from_env()
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd Server/web && poetry run pytest tests/test_configs_serverless.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.configs.serverless'`

- [ ] **Step 3: serverlessモジュールを実装**

`Server/web/api/configs/serverless/__init__.py` — 空ファイル。

`Server/web/api/configs/serverless/constants.py`:

```python
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
```

`Server/web/api/configs/serverless/credentials.py`:

```python
"""
serverless環境ではOPENAI_API_KEY等はLambdaの環境変数として直接注入されるため、
os.environへの再設定は不要。既存 configs/__init__.py のループ互換のため空dictを置く。
"""
ENVBIRONMENT_VALIABLES: dict[str, str] = {}
```

`Server/web/api/configs/serverless/database.py`:

```python
"""
serverless環境のDB設定。DynamoDB移行完了後は未使用となるが、
既存コード（drivers/database.py）のimport互換のため環境変数から読む。
"""
import os

DB_HOST = os.environ.get("DB_HOST", "")
DB_NAME = os.environ.get("DB_NAME", "")
DB_USER = os.environ.get("DB_USER", "")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
```

- [ ] **Step 4: configs/__init__.py に分岐を追加**

`Server/web/api/configs/__init__.py` の `elif APP_ENV == "localhost":` ブロックの直後・`else:` の前に追加:

```python
elif APP_ENV == "serverless":
    from .serverless import constants as env_constants
    from .serverless import credentials as credentials
    from .serverless import database as database
    cache = None
```

**注意**: この時点で `cache` は Task 5 で全環境から削除するため、暫定で `None` を代入して既存コードとの互換を保つ。

- [ ] **Step 5: テストが通ることを確認**

```bash
cd Server/web && poetry run pytest tests/test_configs_serverless.py -v && poetry run pytest -v
```

Expected: 新規2件を含め全件PASS（既存環境の分岐に影響がないこと）

- [ ] **Step 6: Commit**

```bash
git add Server/web/api/configs/serverless Server/web/api/configs/__init__.py Server/web/tests/test_configs_serverless.py
git commit -m "feat: APP_ENV=serverless の環境変数ベース設定モードを追加"
```

---

### Task 5: memcached依存の削除

アプリコードでの使用箇所ゼロを確認済み（2026-07-05 grep調査: configs以外に参照なし）。依存とconfig参照を削除する。

**Files:**
- Modify: `Server/web/pyproject.toml`（python-memcached削除）
- Modify: `Server/web/api/configs/__init__.py`
- Delete: なし（`configs/*/cache.py` はgit管理された環境ファイルのため、削除はproduction反映のタイミングで別途行う。importだけ外す）

- [ ] **Step 1: configs/__init__.py から cache import を削除**

`Server/web/api/configs/__init__.py` — production / development / localhost 各分岐の `from .xxx import cache as cache` の行（3行）と、Task 4 で追加した serverless 分岐の `cache = None` を削除する。

- [ ] **Step 2: 依存を削除**

```bash
cd Server/web && poetry remove python-memcached
```

- [ ] **Step 3: 全テスト + import確認**

```bash
cd Server/web && poetry run pytest -v && poetry run python -c "import api.configs; import api.main; print('import OK')"
```

Expected: 全件PASS + `import OK`

- [ ] **Step 4: Docker回帰確認**

```bash
cd Server && docker-compose build web && docker-compose up -d && sleep 10 && curl -s http://localhost:80/batch/healthcheck && docker-compose down
```

Expected: `{"is_success":true}`

- [ ] **Step 5: Commit**

```bash
git add Server/web/pyproject.toml Server/web/poetry.lock Server/web/api/configs/__init__.py
git commit -m "refactor: 未使用のmemcached依存を削除"
```

---

## 後続プラン（本プランのスコープ外）

1. **DynamoDB移行編** — `t_draft` のDynamoDB DAO実装（moto使用のテスト付き）、routers/services の差し替え、移行スクリプト
2. **バッチLambda化編** — batch-update / batch-create のLambdaエントリポイント分離、batch-createの1起動1件処理化
3. **Terraform編** — Infra/terraform モジュール群（設計書§4の構成）

## Self-Review 結果

- スペック(設計書§6 Phase 2)との対応: Cache-Control化✅ / Mangum✅ / 設定の環境変数化✅ / memcached削除✅ / DynamoDB DAOと1件処理化は後続プランに分離（スコープ宣言済み）✅
- プレースホルダなし・全ステップに実コードとコマンドあり
- 型・シグネチャ整合: `build_put_args` はkeyword-only、`upload_bytes` の呼び出し3箇所すべて keyword で `cache_control` を渡す形に統一
- 既知の既存バグ修正をTask 2 Step 5に明記（create_allのreport CSVキーが常に最後のtheme_infoを参照する問題）
