from api.utils.storage_s3 import build_put_args


def test_build_put_args_minimal():
    args = build_put_args(bucket="b", key="k", data=b"x")
    assert args == {"Bucket": "b", "Key": "k", "Body": b"x"}


def test_build_put_args_with_content_type_and_cache_control():
    args = build_put_args(
        bucket="app.pol-is.jp",
        key="csv/themes.csv",
        data=b"data",
        content_type="text/csv",
        cache_control="max-age=300",
    )
    assert args["ContentType"] == "text/csv"
    assert args["CacheControl"] == "max-age=300"


def test_build_put_args_extra_overrides():
    args = build_put_args(bucket="b", key="k", data=b"x", extra_put_args={"Metadata": {"a": "1"}})
    assert args["Metadata"] == {"a": "1"}
