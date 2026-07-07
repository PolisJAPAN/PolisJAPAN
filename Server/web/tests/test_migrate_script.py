import json

import boto3
import pytest
from moto import mock_aws

from scripts.migrate_drafts_to_dynamodb import row_to_item, migrate, verify

TABLE = "polisjapan-drafts-test"

SAMPLE_ROWS = [
    {
        "id": 5, "title": "t", "origin_url": "u", "origin_html": "<html>大きいHTML</html>",
        "theme_name": "名前", "theme_description": "説明", "theme_comments": "a###br###b",
        "theme_category": 3, "conversation_id": "c5", "report_id": "r5",
        "post_status": 3, "status": 1,
        "create_date": "2026-01-02 03:04:05", "update_date": "2026-01-03 03:04:05",
    },
    {
        "id": 6, "title": "", "origin_url": "", "origin_html": "",
        "theme_name": "削除済み", "theme_description": "", "theme_comments": "",
        "theme_category": 1, "conversation_id": "", "report_id": "",
        "post_status": 101, "status": 0,
        "create_date": "2026-02-02 03:04:05", "update_date": "2026-02-03 03:04:05",
    },
]


def test_row_to_item_excludes_origin_html_and_converts_dates():
    item = row_to_item(SAMPLE_ROWS[0])
    assert item["id"] == 5
    assert item["origin_html"] == ""            # LONGTEXTは移行しない(アーカイブに残る)
    assert item["create_date"] == "2026-01-02T03:04:05"  # MySQL形式 → ISO 8601
    assert item["post_status"] == 3
    assert item["status"] == 1


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-3")
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-northeast-3")
        client.create_table(
            TableName=TABLE,
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "N"},
                {"AttributeName": "post_status", "AttributeType": "N"},
            ],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "post_status-index",
                "KeySchema": [{"AttributeName": "post_status", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="ap-northeast-3").Table(TABLE)


def test_migrate_and_verify(table, tmp_path):
    src = tmp_path / "t_draft.json"
    src.write_text(json.dumps(SAMPLE_ROWS, ensure_ascii=False))

    result = migrate(str(src), TABLE)
    assert result == {"total": 2, "written": 2}

    # 論理削除済み(status=0)も含めて全行移行される（履歴保全のため）
    ok, report = verify(str(src), TABLE)
    assert ok is True
    assert report["source_count"] == 2
    assert report["table_count"] == 2
    assert report["mismatched_ids"] == []


def test_verify_delta_mode_ignores_count_mismatch(table, tmp_path):
    """差分再同期では部分ファイルを投入するため、全件数照合をスキップして行突合のみ行う"""
    # 全量を投入した後、1行だけの差分ファイルで検証する状況を再現
    full = tmp_path / "full.json"
    full.write_text(json.dumps(SAMPLE_ROWS, ensure_ascii=False))
    migrate(str(full), TABLE)

    delta = tmp_path / "delta.json"
    delta.write_text(json.dumps([SAMPLE_ROWS[0]], ensure_ascii=False))

    # 通常モードでは件数不一致(1 vs 2)でFAILする（これがRunbookで誤判断を生む挙動だった）
    ok_full, _ = verify(str(delta), TABLE)
    assert ok_full is False

    # 差分モードでは対象行の突合のみでOKになる
    ok_delta, report = verify(str(delta), TABLE, delta=True)
    assert ok_delta is True
    assert report["mode"] == "delta"
    assert report["mismatched_ids"] == []
