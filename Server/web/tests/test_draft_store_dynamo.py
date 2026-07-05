import boto3
import pytest
from moto import mock_aws

from api.repositories.draft import Draft
from api.repositories.draft_store_dynamo import DynamoDraftStore

TABLE = "polisjapan-drafts-test"


@pytest.fixture
def store(monkeypatch):
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
        yield DynamoDraftStore(table_name=TABLE)


async def test_insert_and_select_by_id(store):
    draft = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="テーマA", theme_description="説明A",
        theme_comments="c1###br###c2", theme_category=1, post_status=2,
    )
    assert isinstance(draft, Draft)
    assert draft.id >= 1
    assert draft.status == 1  # 有効フラグ自動付与
    assert draft.conversation_id == ""

    loaded = await store.select_by_id(draft.id)
    assert loaded is not None
    assert loaded.theme_name == "テーマA"
    assert loaded.post_status == 2
    assert loaded.create_date is not None  # datetimeとして復元される


async def test_select_by_id_not_found_returns_none(store):
    assert await store.select_by_id(999999999) is None


async def test_insert_id_collision_retries(store, monkeypatch):
    # 採番の起点を固定して2連続insert → 2件目は+1リトライで別IDになる
    monkeypatch.setattr("api.repositories.draft_store_dynamo.time.time", lambda: 1751000000.0)
    d1 = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="A", theme_description="", theme_comments="", theme_category=1, post_status=2,
    )
    d2 = await store.insert_draft(
        title="", origin_url="", origin_html="",
        theme_name="B", theme_description="", theme_comments="", theme_category=1, post_status=2,
    )
    assert d1.id == 1751000000
    assert d2.id == 1751000001


async def test_select_all_returns_only_active_sorted(store):
    d1 = await store.insert_draft(title="", origin_url="", origin_html="",
                                  theme_name="A", theme_description="", theme_comments="", theme_category=1, post_status=2)
    d2 = await store.insert_draft(title="", origin_url="", origin_html="",
                                  theme_name="B", theme_description="", theme_comments="", theme_category=2, post_status=3)
    await store.delete_by_id(d2.id)  # 論理削除 → select_allから消える

    drafts = await store.select_all()
    assert [d.id for d in drafts] == [d1.id]


async def _make(store, **kw):
    base = dict(title="", origin_url="", origin_html="",
                theme_name="T", theme_description="", theme_comments="", theme_category=1, post_status=2)
    base.update(kw)
    return await store.insert_draft(**base)


async def test_update_post_status(store):
    d = await _make(store)
    updated = await store.update_post_status(d, 3)
    assert updated.post_status == 3  # ローカルにも反映
    loaded = await store.select_by_id(d.id)
    assert loaded.post_status == 3
    assert loaded.update_date >= loaded.create_date


async def test_update_content_partial(store):
    d = await _make(store, theme_name="旧名", theme_category=1)
    await store.update_content(d, theme_name="新名", theme_description=None,
                               theme_comments=None, theme_category=5)
    loaded = await store.select_by_id(d.id)
    assert loaded.theme_name == "新名"
    assert loaded.theme_category == 5
    assert loaded.theme_description == ""  # None指定は更新しない


async def test_update_post_info(store):
    d = await _make(store)
    await store.update_post_info(d, "conv123", "rep456", 3)
    loaded = await store.select_by_id(d.id)
    assert (loaded.conversation_id, loaded.report_id, loaded.post_status) == ("conv123", "rep456", 3)


async def test_delete_by_id_is_logical(store):
    d = await _make(store)
    await store.delete_by_id(d.id)
    assert await store.select_by_id(d.id) is None          # 有効レコードとしては見えない
    assert await store.select_by_post_status(2) == []      # GSI経由でも見えない
    raw = store._table.get_item(Key={"id": d.id})["Item"]  # 物理的には残っている
    assert int(raw["status"]) == 0
