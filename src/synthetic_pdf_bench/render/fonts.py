from __future__ import annotations

from functools import lru_cache

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

LATIN_FONT = "Helvetica"
LATIN_BOLD_FONT = "Helvetica-Bold"
CJK_FONT = "STSong-Light"


def contains_cjk(text: str) -> bool:
    return any(
        "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        for char in text
    )


@lru_cache(maxsize=1)
def register_fonts() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(CJK_FONT))


def font_for_text(text: str, bold: bool = False) -> str:
    register_fonts()
    if contains_cjk(text):
        return CJK_FONT
    return LATIN_BOLD_FONT if bold else LATIN_FONT
