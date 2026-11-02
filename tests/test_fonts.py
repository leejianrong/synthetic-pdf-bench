from synthetic_pdf_bench.render.fonts import (
    CJK_FONT,
    FONT_FAMILIES,
    contains_cjk,
    font_for_text,
)


def test_cjk_detection() -> None:
    assert contains_cjk("简体中文")
    assert contains_cjk("English and 简体中文")
    assert not contains_cjk("Bahasa Melayu")


def test_font_selection_uses_cjk_font_for_chinese_text() -> None:
    assert font_for_text("English", bold=False) == FONT_FAMILIES["Helvetica"][0]
    assert font_for_text("English", bold=True) == FONT_FAMILIES["Helvetica"][1]
    assert font_for_text("English and 简体中文", bold=True) == CJK_FONT


def test_font_family_selects_matching_regular_and_bold() -> None:
    assert font_for_text("English", family="Times") == "Times-Roman"
    assert font_for_text("English", bold=True, family="Courier") == "Courier-Bold"
