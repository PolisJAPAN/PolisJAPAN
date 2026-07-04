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
