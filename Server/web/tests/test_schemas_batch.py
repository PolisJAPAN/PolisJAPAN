import pytest
from pydantic import ValidationError

from api.schemas.batch import BatchDeleteRequest


def test_delete_request_accepts_epoch_second_id():
    # DynamoDBバックエンドの新規下書きIDはepoch秒（約1.75e9）。
    # 旧上限 le=256 では移行後の下書きが削除不能になるリグレッションを防ぐ
    req = BatchDeleteRequest(access_key="k", t_draft_id=1751000000)
    assert req.t_draft_id == 1751000000


def test_delete_request_accepts_legacy_small_id():
    req = BatchDeleteRequest(access_key="k", t_draft_id=21)
    assert req.t_draft_id == 21


def test_delete_request_rejects_zero():
    with pytest.raises(ValidationError):
        BatchDeleteRequest(access_key="k", t_draft_id=0)
