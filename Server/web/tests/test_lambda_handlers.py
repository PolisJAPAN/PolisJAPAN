from unittest.mock import AsyncMock, patch

from api.services.batch import BatchService


def test_batch_update_handler_returns_result():
    from api.lambda_handlers import batch_update

    with patch.object(BatchService, "initialize_utils", AsyncMock()), \
         patch.object(BatchService, "update_themes", AsyncMock(return_value=3)), \
         patch("api.lambda_handlers.batch_update.create_draft_store", return_value=AsyncMock()):
        result = batch_update.handler({}, None)

    assert result == {"is_success": True, "updated": 3}


def test_batch_create_handler_processes_one():
    from api.lambda_handlers import batch_create

    with patch.object(BatchService, "initialize_utils", AsyncMock()), \
         patch.object(BatchService, "publish_approved_drafts", AsyncMock(return_value=1)) as publish_mock, \
         patch("api.lambda_handlers.batch_create.create_draft_store", return_value=AsyncMock()):
        result = batch_create.handler({}, None)

    assert result == {"is_success": True, "processed": 1}
    publish_mock.assert_awaited_once_with(limit=1)


def test_handler_closes_s3_even_on_error():
    from api.lambda_handlers import batch_update

    s3_mock = AsyncMock()

    async def _init(self):
        self.s3 = s3_mock

    with patch.object(BatchService, "initialize_utils", _init), \
         patch.object(BatchService, "update_themes", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("api.lambda_handlers.batch_update.create_draft_store", return_value=AsyncMock()):
        try:
            batch_update.handler({}, None)
            assert False, "should raise"
        except RuntimeError:
            pass

    s3_mock.close.assert_awaited_once()
