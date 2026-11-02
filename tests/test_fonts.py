from synthetic_pdf_bench.render.fonts import (
    CJK_FONT,
    LATIN_BOLD_FONT,
    LATIN_FONT,
    contains_cjk,
    font_for_text,
)


def test_cjk_detection() -> None:
    assert contains_cjk("简体中文")
    assert contains_cjk("English and 简体中文")
    assert not contains_cjk("Bahasa Melayu")


def test_font_selection_uses_cjk_font_for_chinese_text() -> None:
    assert font_for_text("English", bold=False) == LATIN_FONT
    assert font_for_text("English", bold=True) == LATIN_BOLD_FONT
    assert font_for_text("English and 简体中文", bold=True) == CJK_FONT
