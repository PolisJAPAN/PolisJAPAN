"""ThemeService のうち、外部サービスを呼ばない処理のテスト"""
from api.services.theme import ThemeService


def test_normalize_axis_lines_strips_bullets_and_blanks():
    lines = ["- 推進する立場 ", "", "  ", "- 慎重な立場"]
    assert ThemeService.normalize_axis_lines(lines) == ["推進する立場", "慎重な立場"]


def test_normalize_axis_lines_splits_single_line_with_vs():
    lines = ["学校主導の部活動維持 vs 地域主体の活動への移行"]
    assert ThemeService.normalize_axis_lines(lines) == ["学校主導の部活動維持", "地域主体の活動への移行"]


def test_normalize_axis_lines_splits_single_line_with_slash():
    lines = ["- 在宅勤務を標準とする立場／出社を標準とする立場"]
    assert ThemeService.normalize_axis_lines(lines) == ["在宅勤務を標準とする立場", "出社を標準とする立場"]


def test_normalize_axis_lines_keeps_slash_when_already_two_lines():
    lines = ["- 賛成／推進の立場", "- 反対／慎重の立場"]
    assert ThemeService.normalize_axis_lines(lines) == ["賛成／推進の立場", "反対／慎重の立場"]


def test_normalize_axis_lines_keeps_single_line_without_separator():
    assert ThemeService.normalize_axis_lines(["賛成する立場"]) == ["賛成する立場"]
