from unittest.mock import AsyncMock, patch

from api.services.batch import BatchService, CSV_CACHE_CONTROL

THEMES = [
    {"id": "1", "category": "1", "title": "T1", "description": "d", "conversation_id": "c1",
     "report_id": "r1", "votes": "10", "comments": "2", "create_date": "2026-01-01 00:00:00"},
    {"id": "2", "category": "2", "title": "T2", "description": "d", "conversation_id": "c2",
     "report_id": "r2", "votes": "5", "comments": "1", "create_date": "2026-01-01 00:00:00"},
]


def _report(votes_list):
    # comment-groups.csv相当: 1行=1コメント
    return [{"comment-id": str(i), "total-votes": str(v)} for i, v in enumerate(votes_list)]


async def test_update_themes_uploads_only_changed():
    service = BatchService()
    service.s3 = AsyncMock()

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([6, 6])),   # c1: 合計12票 ≠ 10 → 更新対象
             ("csv2", _report([5])),      # c2: 合計5票 = 5 → 変化なし
         ])):
        updated = await service.update_themes()

    assert updated == 1
    # report_c1 と themes.csv の2回のみアップロード
    keys = [call.args[0] for call in service.s3.upload_bytes.await_args_list]
    assert keys == ["csv/report/report_c1.csv", "csv/themes.csv"]
    # Cache-Controlが必ず付与される
    for call in service.s3.upload_bytes.await_args_list:
        assert call.kwargs["cache_control"] == CSV_CACHE_CONTROL
    # themes.csv には更新後の票数が反映されている
    themes_body = service.s3.upload_bytes.await_args_list[1].args[1].decode("utf-8")
    assert "12" in themes_body


async def test_update_themes_no_change_no_upload():
    service = BatchService()
    service.s3 = AsyncMock()

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([10])),
             ("csv2", _report([5])),
         ])):
        updated = await service.update_themes()

    assert updated == 0
    service.s3.upload_bytes.assert_not_awaited()


from api.repositories.draft import Draft


def _draft(id_, name):
    return Draft(id=id_, theme_name=name, theme_description="説明",
                 theme_comments="A###br###B", theme_category=1, post_status=2)


def _service_with_store(drafts):
    service = BatchService()
    service.s3 = AsyncMock()
    service.draft_store = AsyncMock()
    service.draft_store.select_by_post_status = AsyncMock(return_value=drafts)
    return service


async def test_publish_approved_drafts_limit_1():
    drafts = [_draft(1, "先"), _draft(2, "後")]
    service = _service_with_store(drafts)

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [{"id": "9"}]))), \
         patch.object(BatchService, "create_theme", AsyncMock(return_value=(
             "report-csv", {"id": "10", "conversation_id": "c10", "report_id": "r10"}))) as create_mock:
        processed = await service.publish_approved_drafts(limit=1)

    assert processed == 1
    create_mock.assert_awaited_once()                      # 1件しか作らない
    service.draft_store.update_post_info.assert_awaited_once()
    args = service.draft_store.update_post_info.await_args.args
    assert args[0].id == 1                                 # 先頭(最古)の下書きが対象
    assert args[1:] == ("c10", "r10", 3)                   # POSTED=3
    service.draft_store.commit.assert_awaited_once()

    # themes.csv 1回 + report 1回
    keys = [call.args[0] for call in service.s3.upload_bytes.await_args_list]
    assert keys == ["csv/themes.csv", "csv/report/report_c10.csv"]


async def test_publish_approved_drafts_empty_returns_zero():
    service = _service_with_store([])
    with patch.object(BatchService, "get_theme_csv", AsyncMock()) as get_csv_mock:
        processed = await service.publish_approved_drafts()
    assert processed == 0
    get_csv_mock.assert_not_awaited()      # 対象ゼロならS3にも触らない
    service.s3.upload_bytes.assert_not_awaited()


async def test_publish_approved_drafts_rolls_back_on_store_error():
    drafts = [_draft(1, "X")]
    service = _service_with_store(drafts)
    service.draft_store.update_post_info = AsyncMock(side_effect=RuntimeError("boom"))

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", []))), \
         patch.object(BatchService, "create_theme", AsyncMock(return_value=("csv", {"id": "1", "conversation_id": "c", "report_id": "r"}))):
        try:
            await service.publish_approved_drafts()
            assert False, "should raise"
        except RuntimeError:
            pass

    service.draft_store.rollback.assert_awaited_once()
