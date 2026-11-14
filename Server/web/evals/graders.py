"""AI 出力の評価のうち、コードで判定する基準

各関数は、基準の ID をキー、合否を値にした dict を返す。外部サービスは呼ばない。
基準の意味と合格ラインは docs/サーバー設計.md の「AI 出力の評価」を参照。
"""
import re

AXIS_COUNT = 2
"""画面の立場の入力欄の数"""
AXIS_MAX_LENGTH = 40
"""プロンプトで指定している立場の文字数"""
COMMENTS_PER_AXIS = 4
"""プロンプトで指定している、立場 1 つあたりの意見の数"""
COMMENT_TARGET_LENGTH = 80
"""プロンプトで指定している意見の文字数"""
COMMENT_LIMIT_LENGTH = 140
"""pol.is が受け付ける意見の文字数"""
DESCRIPTION_LIMIT_LENGTH = 200
"""画面と API が受け付ける説明の文字数"""
LATENCY_LIMIT_SECONDS = 20.0
"""1 回の生成にかけてよい秒数。API Gateway は約 30 秒で応答を打ち切る"""

_LEADING_MARK = re.compile(r"^\s*(?:[-・*●■]|\d+[.．)）、]|[①-⑳])")


def _is_clean_line(text: str) -> bool:
    """空でなく、改行と行頭の記号・番号を含まない"""
    return bool(text.strip()) and "\n" not in text and not _LEADING_MARK.match(text)


def grade_axis(axis_list: list[str]) -> dict[str, bool]:
    """立場の生成結果を判定する"""
    return {
        "axis_count": len(axis_list) == AXIS_COUNT,
        "axis_length": bool(axis_list) and all(len(axis) <= AXIS_MAX_LENGTH for axis in axis_list),
        "axis_distinct": len(axis_list) >= 2 and len(set(axis_list)) == len(axis_list),
        "axis_clean": bool(axis_list) and all(_is_clean_line(axis) for axis in axis_list),
    }


def grade_comments(comments: list[str], axis_count: int) -> dict[str, bool]:
    """意見の生成結果を判定する"""
    return {
        "comments_count": axis_count > 0 and len(comments) == COMMENTS_PER_AXIS * axis_count,
        "comments_length_target": bool(comments) and all(len(c) <= COMMENT_TARGET_LENGTH for c in comments),
        "comments_length_limit": bool(comments) and all(len(c) <= COMMENT_LIMIT_LENGTH for c in comments),
        "comments_clean": bool(comments) and all(_is_clean_line(c) for c in comments),
        "comments_unique": bool(comments) and len(set(comments)) == len(comments),
    }


def grade_description(description: str) -> dict[str, bool]:
    """説明の生成結果を判定する"""
    text = description.strip()
    return {
        "description_limit": 0 < len(text) <= DESCRIPTION_LIMIT_LENGTH,
        "description_question": text.endswith(("？", "?")),
        "description_single": bool(text) and "\n" not in text,
    }


def grade_latency(step: str, seconds: float | None) -> dict[str, bool]:
    """生成にかかった時間を判定する。seconds が None（生成の失敗）は不合格"""
    return {f"latency_{step}": seconds is not None and seconds <= LATENCY_LIMIT_SECONDS}


THRESHOLDS: dict[str, float] = {
    # 画面や pol.is が受け付けない出力と、公開できない内容は 1 件も許さない
    "comments_length_limit": 1.0,
    "description_limit": 1.0,
    "judge_safe": 1.0,
    # 画面の入力欄に合う形
    "axis_count": 0.9,
    "axis_length": 0.9,
    "axis_distinct": 0.9,
    "axis_clean": 0.9,
    "comments_count": 0.9,
    "comments_clean": 0.9,
    "comments_unique": 0.9,
    "description_question": 0.9,
    "description_single": 0.9,
    # 応答の速さ
    "latency_axis": 0.9,
    "latency_comments": 0.9,
    "latency_description": 0.9,
    # プロンプトの目安（超えても投稿はできる）
    "comments_length_target": 0.8,
    # 内容（モデルによる判定）
    "judge_axis_opposed": 0.9,
    "judge_comments_relevant": 0.9,
    "judge_comments_balanced": 0.8,
    "judge_description_faithful": 0.9,
}
"""基準ごとの合格ライン（合格したケースの割合）"""


def summarize(records: list[dict[str, bool]], thresholds: dict[str, float] | None = None) -> list[dict]:
    """
    ケースごとの判定結果を、基準ごとの合格率にまとめる

    Args:
        records: ケースごとの {基準 ID: 合否}
        thresholds: 基準ごとの合格ライン。省略すると THRESHOLDS

    Returns:
        基準ごとの {id, passed, total, rate, threshold, ok}。判定結果に現れた基準だけを返す
    """
    thresholds = THRESHOLDS if thresholds is None else thresholds
    rows = []
    for criterion, threshold in thresholds.items():
        values = [record[criterion] for record in records if criterion in record]
        if not values:
            continue
        rate = sum(values) / len(values)
        rows.append({
            "id": criterion,
            "passed": sum(values),
            "total": len(values),
            "rate": rate,
            "threshold": threshold,
            "ok": rate >= threshold,
        })
    return rows
