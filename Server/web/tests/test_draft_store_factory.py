from unittest.mock import AsyncMock, MagicMock, patch

import api.configs as configs
from api.repositories import create_draft_store
from api.repositories.draft_store_dynamo import DynamoDraftStore
from api.repositories.draft_store_mysql import MySQLDraftStore


def test_factory_returns_mysql_by_default(monkeypatch):
    monkeypatch.setattr(configs.constants, "DATA_BACKEND", "mysql", raising=False)
    store = create_draft_store(db_session=MagicMock())
    assert isinstance(store, MySQLDraftStore)


def test_factory_returns_dynamo_when_configured(monkeypatch):
    monkeypatch.setattr(configs.constants, "DATA_BACKEND", "dynamodb", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")
    from moto import mock_aws
    with mock_aws():
        store = create_draft_store()
        assert isinstance(store, DynamoDraftStore)


async def test_mysql_store_delegates_to_cruds():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    store = MySQLDraftStore(db)

    orm_row = MagicMock(id=1, post_status=2)
    with patch("api.repositories.draft_store_mysql.cruds") as cruds_mock:
        cruds_mock.TDraft.select_by_post_status = AsyncMock(return_value=[orm_row])
        result = await store.select_by_post_status(2)
        cruds_mock.TDraft.select_by_post_status.assert_awaited_once_with(db, 2)
        assert result == [orm_row]

    await store.commit()
    db.commit.assert_awaited_once()
    await store.rollback()
    db.rollback.assert_awaited_once()
