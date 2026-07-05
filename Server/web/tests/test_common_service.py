import pytest

from api.core.common_service import CommonService


@pytest.fixture(autouse=True)
def aws_region(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")


async def test_initialize_utils_uses_default_bucket(monkeypatch):
    monkeypatch.delenv("CSV_BUCKET", raising=False)
    service = CommonService()
    await service.initialize_utils()
    try:
        assert service.s3.bucket == "app.pol-is.jp"
    finally:
        await service.s3.close()


async def test_initialize_utils_respects_csv_bucket_env(monkeypatch):
    # E2Eテストで本番CSVを汚さないよう、サンドボックスバケットに向け替えられること
    monkeypatch.setenv("CSV_BUCKET", "polisjapan-e2e-sandbox")
    service = CommonService()
    await service.initialize_utils()
    try:
        assert service.s3.bucket == "polisjapan-e2e-sandbox"
    finally:
        await service.s3.close()
