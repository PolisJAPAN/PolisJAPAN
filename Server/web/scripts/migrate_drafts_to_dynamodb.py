"""
t_draft(MySQL) → DynamoDB 移行スクリプト。

使い方:
  1. 本番MySQLからJSONエクスポート（カットオーバーRunbook参照）:
     docker exec PolisJAPAN_db mysql -uapp_user -p... app_db \
       -e "SELECT * FROM t_draft" 等で取得しJSON配列ファイル化
  2. poetry run python -m scripts.migrate_drafts_to_dynamodb t_draft.json polisjapan-drafts
  3. 末尾に検証結果（件数照合・全属性突合）が出力される。NGなら終了コード1

方針:
  - origin_html は移行しない（休眠スクレイピング機能用の大容量LONGTEXT。全量はS3アーカイブに残る）
  - status=0（論理削除済み）も含め全行を移行する（削除履歴の保全）
  - 日時は "YYYY-MM-DD HH:MM:SS" → ISO 8601 に変換
"""
import json
import sys

import boto3

MIGRATE_FIELDS = [
    "id", "title", "origin_url", "theme_name", "theme_description",
    "theme_comments", "theme_category", "conversation_id", "report_id",
    "post_status", "status",
]
INT_FIELDS = {"id", "theme_category", "post_status", "status"}
DATE_FIELDS = ["create_date", "update_date"]


def _to_iso(mysql_datetime: str) -> str:
    """'2026-01-02 03:04:05' → '2026-01-02T03:04:05'（既にISOならそのまま）。"""
    return mysql_datetime.replace(" ", "T") if mysql_datetime else None


def row_to_item(row: dict) -> dict:
    """MySQLの1行をDynamoDBアイテムに変換する。origin_htmlは空文字に落とす。"""
    item = {}
    for f in MIGRATE_FIELDS:
        value = row.get(f)
        item[f] = int(value) if f in INT_FIELDS else (value if value is not None else "")
    item["origin_html"] = ""
    for f in DATE_FIELDS:
        item[f] = _to_iso(row.get(f))
    return item


def migrate(source_json_path: str, table_name: str) -> dict:
    """JSONファイルの全行をDynamoDBにbatch書き込みする。"""
    rows = json.loads(open(source_json_path, encoding="utf-8").read())
    table = boto3.resource("dynamodb").Table(table_name)
    written = 0
    with table.batch_writer(overwrite_by_pkeys=["id"]) as batch:
        for row in rows:
            batch.put_item(Item=row_to_item(row))
            written += 1
    return {"total": len(rows), "written": written}


def verify(source_json_path: str, table_name: str) -> tuple[bool, dict]:
    """件数照合 + 全行の属性突合（origin_html以外）を行う。"""
    rows = json.loads(open(source_json_path, encoding="utf-8").read())
    table = boto3.resource("dynamodb").Table(table_name)

    items: dict[int, dict] = {}
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            items[int(item["id"])] = item
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    mismatched = []
    for row in rows:
        expected = row_to_item(row)
        actual = items.get(int(row["id"]))
        if actual is None:
            mismatched.append(int(row["id"]))
            continue
        for key, value in expected.items():
            actual_value = actual.get(key)
            if key in INT_FIELDS:
                actual_value = int(actual_value)
            if actual_value != value:
                mismatched.append(int(row["id"]))
                break

    report = {
        "source_count": len(rows),
        "table_count": len(items),
        "mismatched_ids": mismatched,
    }
    ok = len(rows) == len(items) and not mismatched
    return ok, report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m scripts.migrate_drafts_to_dynamodb <t_draft.json> <table_name>")
        sys.exit(2)
    source, table_name = sys.argv[1], sys.argv[2]

    print(f"migrate: {source} -> {table_name}")
    print(json.dumps(migrate(source, table_name), ensure_ascii=False))

    ok, report = verify(source, table_name)
    print(json.dumps(report, ensure_ascii=False))
    print("VERIFY OK" if ok else "VERIFY FAILED")
    sys.exit(0 if ok else 1)
