from __future__ import annotations

from functools import lru_cache

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# family -> (regular, bold); all are ReportLab built-ins, so no font files are needed.
FONT_FAMILIES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold"),
    "Times": ("Times-Roman", "Times-Bold"),
    "Courier": ("Courier", "Courier-Bold"),
}
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


def font_for_text(text: str, bold: bool = False, family: str = "Helvetica") -> str:
    register_fonts()
    if contains_cjk(text):
        return CJK_FONT
    return FONT_FAMILIES[family][bold]
