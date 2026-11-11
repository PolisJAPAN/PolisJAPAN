import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import api.models.types as types
from api.lambda_handlers import backlog_monitor
from api.services.batch import BatchService
from api.utils.time import Time


def _store(failed_titles=(), pending=0):
    """post_statusごとに下書きリストを返すストアのモック。"""
    by_status = {
        types.PostStatus.FAILED.value: [SimpleNamespace(theme_name=t) for t in failed_titles],
        types.PostStatus.APPROVED.value: [SimpleNamespace(theme_name=f"p{i}") for i in range(pending)],
    }
    store = AsyncMock()
    store.select_by_post_status = AsyncMock(side_effect=lambda status: by_status[status])
    return store


def _jst(hour, minute):
    return datetime(2026, 11, 12, hour, minute, 40, tzinfo=Time.TZ_TOKYO)


def _emf(capsys):
    """標準出力からEMFの1行を取り出す。"""
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith('{"_aws"')]
    assert len(lines) == 1
    return json.loads(lines[0])


def test_emit_metrics_writes_emf_line(capsys):
    backlog_monitor.emit_metrics(failed=2, pending=5, published=1)

    emf = _emf(capsys)
    directive = emf["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "PolisJAPAN/Batch"
    assert directive["Dimensions"] == [["FunctionName"]]
    assert {m["Name"] for m in directive["Metrics"]} == {"FailedDrafts", "PendingDrafts", "PublishedDrafts"}
    assert emf["FunctionName"] == "polisjapan-batch-create"
    assert (emf["FailedDrafts"], emf["PendingDrafts"], emf["PublishedDrafts"]) == (2, 5, 1)


def test_report_emits_counts_from_store(capsys):
    asyncio.run(backlog_monitor.report(_store(["a", "b"], pending=3), published=1, started_at=_jst(12, 14)))

    emf = _emf(capsys)
    assert (emf["FailedDrafts"], emf["PendingDrafts"], emf["PublishedDrafts"]) == (2, 3, 1)


def test_is_reminder_window_only_first_slot_of_9am():
    assert backlog_monitor.is_reminder_window(_jst(9, 0))
    assert backlog_monitor.is_reminder_window(_jst(9, 14))
    assert not backlog_monitor.is_reminder_window(_jst(9, 15))
    assert not backlog_monitor.is_reminder_window(_jst(8, 59))
    assert not backlog_monitor.is_reminder_window(_jst(21, 14))


def test_report_sends_reminder_in_window_when_failed(monkeypatch):
    monkeypatch.setenv("ALERTS_TOPIC_ARN", "arn:aws:sns:ap-northeast-3:0:polisjapan-alerts")
    sns = MagicMock()
    with patch("api.lambda_handlers.backlog_monitor.boto3.client", return_value=sns) as client:
        asyncio.run(backlog_monitor.report(_store(["教養とは", "将棋は運ゲーか"]), 0, _jst(9, 14)))

    client.assert_called_once_with("sns")
    kwargs = sns.publish.call_args.kwargs
    assert kwargs["TopicArn"] == "arn:aws:sns:ap-northeast-3:0:polisjapan-alerts"
    assert "2件" in kwargs["Subject"]
    assert "教養とは" in kwargs["Message"] and "将棋は運ゲーか" in kwargs["Message"]


def test_report_does_not_send_reminder_when_not_needed(monkeypatch):
    monkeypatch.setenv("ALERTS_TOPIC_ARN", "arn:aws:sns:ap-northeast-3:0:polisjapan-alerts")
    with patch("api.lambda_handlers.backlog_monitor.boto3.client") as client:
        asyncio.run(backlog_monitor.report(_store([]), 0, _jst(9, 14)))          # 失敗なし
        asyncio.run(backlog_monitor.report(_store(["a"]), 0, _jst(9, 29)))       # 送信枠の外
        monkeypatch.delenv("ALERTS_TOPIC_ARN")
        asyncio.run(backlog_monitor.report(_store(["a"]), 0, _jst(9, 14)))       # 通知先未設定

    client.assert_not_called()


def test_build_reminder_truncates_long_list_and_subject_is_sns_safe():
    titles = [f"テーマ{i}" for i in range(25)]
    subject, message = backlog_monitor.build_reminder(titles)

    assert "テーマ19" in message and "テーマ20" not in message
    assert "ほか 5 件" in message
    # SNSの件名は100文字未満・改行不可
    assert len(subject) < 100 and "\n" not in subject


def test_report_swallows_errors():
    store = AsyncMock()
    store.select_by_post_status = AsyncMock(side_effect=RuntimeError("dynamo down"))

    asyncio.run(backlog_monitor.report(store, 0, _jst(9, 14)))  # 例外を出さない


def test_batch_create_handler_reports_backlog_on_success_and_failure():
    from api.lambda_handlers import batch_create

    for publish, expected_published in ((AsyncMock(return_value=1), 1), (AsyncMock(side_effect=RuntimeError("boom")), 0)):
        store = _store(["a"])
        with patch.object(BatchService, "initialize_utils", AsyncMock()), \
             patch.object(BatchService, "publish_approved_drafts", publish), \
             patch("api.lambda_handlers.batch_create.create_draft_store", return_value=store), \
             patch("api.lambda_handlers.batch_create.backlog_monitor.report", AsyncMock()) as report:
            try:
                batch_create.handler({}, None)
            except RuntimeError:
                pass

        assert report.await_args.args[0] is store
        assert report.await_args.args[1] == expected_published
