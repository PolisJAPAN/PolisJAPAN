"""theme/post_draft のアクセスキー検証と初期ステータスのテスト"""
from unittest.mock import AsyncMock, MagicMock

import pytest

import api.configs as configs
import api.models.types as types
from api.routers import theme as theme_router
from api.schemas.theme import ThemePostDraftErrorResponses, ThemePostDraftRequest


def _request_body(access_key: str) -> ThemePostDraftRequest:
    return ThemePostDraftRequest(
        access_key=access_key,
        theme="テーマ",
        comments="意見1",
        description="説明",
        category=1,
    )


def _mock_request() -> MagicMock:
    request = MagicMock()
    request.state.service = MagicMock()
    request.state.service.draft_store = MagicMock()
    request.state.service.draft_store.insert_draft = AsyncMock(return_value=MagicMock())
    request.state.service.draft_store.commit = AsyncMock()
    request.state.service.draft_store.rollback = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_post_draft_rejects_invalid_access_key():
    request = _mock_request()

    with pytest.raises(ThemePostDraftErrorResponses.InvalidAccessKeyError):
        await theme_router.post_draft(request, _request_body("wrong-key"))

    request.state.service.draft_store.insert_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_draft_inserts_as_generated_with_valid_key():
    request = _mock_request()

    result = await theme_router.post_draft(
        request, _request_body(configs.constants.USER_ACCESS_KEY)
    )

    assert result.is_success is True
    kwargs = request.state.service.draft_store.insert_draft.await_args.kwargs
    assert kwargs["post_status"] == types.PostStatus.GENERATED.value
    assert kwargs["theme_name"] == "テーマ"
    request.state.service.draft_store.commit.assert_awaited_once()
