"""ThemePostDraftRequest の文字数バリデーションのテスト"""
import pytest
from pydantic import ValidationError

from api.schemas.theme import ThemePostDraftRequest


def _make(theme="テーマ", description="説明", **kw):
    return ThemePostDraftRequest(
        access_key="k", theme=theme, comments="c", description=description, category=1, **kw
    )


def test_theme_80_chars_accepted():
    assert _make(theme="あ" * 80).theme == "あ" * 80


def test_theme_81_chars_rejected():
    with pytest.raises(ValidationError):
        _make(theme="あ" * 81)


def test_description_200_chars_accepted():
    assert _make(description="い" * 200).description == "い" * 200


def test_description_201_chars_rejected():
    with pytest.raises(ValidationError):
        _make(description="い" * 201)
