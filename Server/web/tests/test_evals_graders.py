"""AI 出力の評価のうち、コードで判定する基準のテスト"""
from evals import graders


def test_grade_axis_passes_two_clean_stances():
    assert all(graders.grade_axis(["在宅勤務を標準とする立場", "出社を標準とする立場"]).values())


def test_grade_axis_fails_on_single_stance():
    grades = graders.grade_axis(["在宅勤務を標準とする立場"])
    assert grades["axis_count"] is False
    assert grades["axis_distinct"] is False


def test_grade_axis_fails_on_long_or_marked_stance():
    grades = graders.grade_axis(["あ" * 41, "- 出社を標準とする立場"])
    assert grades["axis_length"] is False
    assert grades["axis_clean"] is False


def test_grade_axis_fails_on_empty():
    assert not any(graders.grade_axis([]).values())


def test_grade_comments_checks_count_and_lengths():
    comments = ["意見" + str(i) for i in range(8)]
    assert all(graders.grade_comments(comments, 2).values())
    assert graders.grade_comments(comments[:7], 2)["comments_count"] is False
    long_comments = comments[:7] + ["あ" * 81]
    grades = graders.grade_comments(long_comments, 2)
    assert grades["comments_length_target"] is False
    assert grades["comments_length_limit"] is True
    assert graders.grade_comments(comments[:7] + ["あ" * 141], 2)["comments_length_limit"] is False


def test_grade_comments_detects_numbering_and_duplicates():
    grades = graders.grade_comments(["1. 番号つき", "同じ意見", "同じ意見", "別の意見"], 1)
    assert grades["comments_clean"] is False
    assert grades["comments_unique"] is False


def test_grade_description_checks_limit_and_question():
    assert all(graders.grade_description("背景の説明。どう考えるべきだろうか？").values())
    assert graders.grade_description("あ" * 201)["description_limit"] is False
    assert graders.grade_description("言い切りで終わる。")["description_question"] is False
    assert graders.grade_description("一段落目。\n二段落目？")["description_single"] is False
    assert not any(graders.grade_description("").values())


def test_grade_latency():
    assert graders.grade_latency("axis", 5.0) == {"latency_axis": True}
    assert graders.grade_latency("axis", 25.0) == {"latency_axis": False}
    assert graders.grade_latency("axis", None) == {"latency_axis": False}


def test_summarize_compares_rate_with_threshold():
    records = [{"a": True, "b": True}, {"a": False, "b": True}, {"b": False}]
    rows = graders.summarize(records, {"a": 0.5, "b": 0.9, "unused": 1.0})
    assert [row["id"] for row in rows] == ["a", "b"]
    assert rows[0] == {"id": "a", "passed": 1, "total": 2, "rate": 0.5, "threshold": 0.5, "ok": True}
    assert rows[1]["ok"] is False
