from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api import utils
from api.repositories.draft import Draft
from api.services.batch import THEME_HEADERS, BatchService, CSV_CACHE_CONTROL
from api.utils.storage_s3 import StorageS3Error, StorageS3PreconditionError

THEMES = [
    {"id": "1", "category": "1", "title": "T1", "description": "d", "conversation_id": "c1",
     "report_id": "r1", "votes": "10", "comments": "2", "create_date": "2026-01-01 00:00:00"},
    {"id": "2", "category": "2", "title": "T2", "description": "d", "conversation_id": "c2",
     "report_id": "r2", "votes": "5", "comments": "1", "create_date": "2026-01-01 00:00:00"},
]

FIXED_NOW = utils.Time.from_mysql_datetime_str("2026-07-08 12:34:56", utils.Time.TZ_TOKYO)
FIXED_MINUTE = "2026-07-08 12:34"


def _themes_csv_bytes(themes):
    return utils.CSV.to_csv(themes, THEME_HEADERS).encode("utf-8")


def _report(votes_list):
    # comment-groups.csv相当: 1行=1コメント
    return [{"comment-id": str(i), "total-votes": str(v)} for i, v in enumerate(votes_list)]


def _service():
    service = BatchService()
    service.s3 = AsyncMock()
    # write_themes_csv が読む最新CSV（楽観ロックの取得側）
    service.s3.get_bytes_and_etag = AsyncMock(return_value=(_themes_csv_bytes(THEMES), '"etag-1"'))
    return service


def _written_themes_rows(service):
    """write_themes_csv がアップロードした themes.csv をパースして id→行 の辞書で返す。"""
    call = service.s3.upload_bytes.call_args_list[-1]
    assert call.args[0] == "csv/themes.csv"
    return {r["id"]: r for r in utils.CSV.parse_csv(call.args[1].decode("utf-8"))}


async def test_update_themes_uploads_only_changed():
    service = _service()

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
    # themes.csv は楽観ロック付き（If-Match）で、更新後の票数が反映されている
    themes_call = service.s3.upload_bytes.await_args_list[1]
    assert themes_call.kwargs["if_match"] == '"etag-1"'
    assert "12" in themes_call.args[1].decode("utf-8")


async def test_update_themes_no_change_no_upload():
    service = _service()

    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([5, 5])),  # c1: 10票/2コメント → THEMES[0]と一致（変化なし）
             ("csv2", _report([5])),
         ])):
        updated = await service.update_themes()

    assert updated == 0
    service.s3.upload_bytes.assert_not_awaited()


async def test_update_themes_stamps_updated_at_on_vote_only_change():
    service = _service()
    with patch.object(utils.Time, "now", classmethod(lambda cls: FIXED_NOW)), \
         patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([6, 6])),  # c1: 12票/2コメント → 票のみ変化
             ("csv2", _report([5])),     # c2: 5票/1コメント → 変化なし
         ])):
        count = await service.update_themes()

    assert count == 1
    rows = _written_themes_rows(service)
    assert rows["1"]["updated_at"] == FIXED_MINUTE
    assert rows["1"]["commented_at"] == ""  # コメント数は増えていない
    assert rows["1"]["created_at"] == ""    # 旧データは空白のまま
    assert rows["2"]["updated_at"] == ""    # 変化なしの行は空白のまま


async def test_update_themes_stamps_both_on_comment_increase():
    service = _service()
    with patch.object(utils.Time, "now", classmethod(lambda cls: FIXED_NOW)), \
         patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([5, 5])),      # c1: 10票/2コメント → 変化なし
             ("csv2", _report([3, 2])),      # c2: 5票/2コメント → コメント増（票は同数）
         ])):
        count = await service.update_themes()

    assert count == 1
    rows = _written_themes_rows(service)
    assert rows["2"]["commented_at"] == FIXED_MINUTE
    assert rows["2"]["updated_at"] == FIXED_MINUTE


async def test_update_themes_comment_only_change_is_detected():
    """現行の「投票数のみ」検知では拾えなかった、コメント数だけの変化も更新対象になる。"""
    service = _service()
    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([10, 0, 0])),  # c1: 10票/3コメント → コメントのみ増
             ("csv2", _report([5])),         # c2: 変化なし
         ])):
        count = await service.update_themes()

    assert count == 1


async def test_write_themes_csv_retries_on_conflict_with_fresh_data():
    """書き込み競合時は最新CSVを再取得してmutateを適用し直す（公開直後のテーマを消さない）"""
    service = BatchService()
    service.s3 = AsyncMock()

    stale = [THEMES[0].copy()]
    # 競合後の最新版には、並行するbatch-createが追記したテーマ(c9)が含まれている
    fresh = [THEMES[0].copy(), {"id": "9", "category": "1", "title": "並行追加", "description": "",
                                "conversation_id": "c9", "report_id": "r9", "votes": "0",
                                "comments": "1", "create_date": "2026-07-05 00:00:00"}]
    service.s3.get_bytes_and_etag = AsyncMock(side_effect=[
        (_themes_csv_bytes(stale), '"etag-old"'),
        (_themes_csv_bytes(fresh), '"etag-new"'),
    ])
    service.s3.upload_bytes = AsyncMock(side_effect=[StorageS3PreconditionError("conflict"), None])

    new_row = {"id": "10", "category": "2", "title": "新規", "description": "",
               "conversation_id": "c10", "report_id": "r10", "votes": "0",
               "comments": "1", "create_date": "2026-07-05 00:00:00"}
    result = await service.write_themes_csv(lambda current: current + [new_row])

    assert service.s3.upload_bytes.await_count == 2
    # 2回目の書き込みは最新版(c9入り)ベース + 新規行
    second_body = service.s3.upload_bytes.await_args_list[1].args[1].decode("utf-8")
    assert "c9" in second_body and "c10" in second_body
    assert service.s3.upload_bytes.await_args_list[1].kwargs["if_match"] == '"etag-new"'
    assert [row["conversation_id"] for row in result] == ["c1", "c9", "c10"]


async def test_write_themes_csv_gives_up_after_max_attempts():
    service = BatchService()
    service.s3 = AsyncMock()
    service.s3.get_bytes_and_etag = AsyncMock(return_value=(_themes_csv_bytes(THEMES), '"e"'))
    service.s3.upload_bytes = AsyncMock(side_effect=StorageS3PreconditionError("conflict"))

    with pytest.raises(StorageS3Error):
        await service.write_themes_csv(lambda current: current, max_attempts=3)
    assert service.s3.upload_bytes.await_count == 3


def _draft(id_, name):
    return Draft(id=id_, theme_name=name, theme_description="説明",
                 theme_comments="A###br###B", theme_category=1, post_status=2)


def _service_with_store(drafts):
    service = _service()
    service.draft_store = AsyncMock()
    service.draft_store.select_by_post_status = AsyncMock(return_value=drafts)
    return service


async def test_publish_approved_drafts_limit_1():
    drafts = [_draft(1, "先"), _draft(2, "後")]
    service = _service_with_store(drafts)

    # create_theme_on_polis（Selenium操作部分）のみモックし、create_theme本体（id採番・日時スタンプ）は実処理を通す
    polis_result = {"id": None, "category": "1", "title": "先", "description": "説明",
                     "conversation_id": "c10", "report_id": "r10", "votes": "0",
                     "comments": 2, "create_date": "2025-09-12"}

    with patch.object(utils.Time, "now", classmethod(lambda cls: FIXED_NOW)), \
         patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [{"id": "9"}]))), \
         patch.object(BatchService, "create_theme_on_polis", MagicMock(return_value=polis_result)) as create_mock, \
         patch.object(BatchService, "get_report_csv", AsyncMock(return_value=("report-csv", []))):
        processed = await service.publish_approved_drafts(limit=1)

    assert processed == 1
    create_mock.assert_called_once()                        # 1件しか作らない
    service.draft_store.update_post_info.assert_awaited_once()
    args = service.draft_store.update_post_info.await_args.args
    assert args[0].id == 1                                 # 先頭(最古)の下書きが対象
    assert args[1:] == ("c10", "r10", 3)                   # POSTED=3
    service.draft_store.commit.assert_awaited_once()

    # themes.csv(楽観ロック) 1回 + report 1回
    keys = [call.args[0] for call in service.s3.upload_bytes.await_args_list]
    assert keys == ["csv/themes.csv", "csv/report/report_c10.csv"]
    # 新テーマ行は「最新の」themes.csv（get_bytes_and_etagの内容）に追記される
    themes_body = service.s3.upload_bytes.await_args_list[0].args[1].decode("utf-8")
    assert "c10" in themes_body and "c1" in themes_body

    # 新規テーマ行の3列は作成時刻(FIXED_NOW)で初期化される
    themes_rows = {r["id"]: r for r in utils.CSV.parse_csv(themes_body)}
    assert themes_rows["10"]["created_at"] == FIXED_MINUTE
    assert themes_rows["10"]["commented_at"] == FIXED_MINUTE
    assert themes_rows["10"]["updated_at"] == FIXED_MINUTE


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
        with pytest.raises(RuntimeError):
            await service.publish_approved_drafts()

    service.draft_store.rollback.assert_awaited_once()
