from __future__ import annotations

import os
from functools import lru_cache

import matplotlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

# family -> (regular, bold). Helvetica, Times and Courier are ReportLab built-ins; the rest are TrueType files that ship with matplotlib
# (DejaVu, STIX, Computer Modern), so no font dependency is added.
FONT_FAMILIES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold"),
    "Times": ("Times-Roman", "Times-Bold"),
    "Courier": ("Courier", "Courier-Bold"),
    "DejaVuSans": ("DejaVuSans", "DejaVuSans-Bold"),
    "DejaVuSerif": ("DejaVuSerif", "DejaVuSerif-Bold"),
    "STIX": ("STIXGeneral", "STIXGeneralBol"),
    "ComputerModern": ("cmr10", "cmb10"),
}
TRUETYPE = {"DejaVuSans", "DejaVuSans-Bold", "DejaVuSerif", "DejaVuSerif-Bold", "STIXGeneral", "STIXGeneralBol", "cmr10", "cmb10"}
FALLBACK = {"cmr10": "DejaVuSerif", "cmb10": "DejaVuSerif-Bold"}  # the Computer Modern files lack some accented letters
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
    folder = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    for name in TRUETYPE:
        pdfmetrics.registerFont(TTFont(name, os.path.join(folder, f"{name}.ttf")))


def _has_glyphs(font: str, text: str) -> bool:
    return all(ord(char) in pdfmetrics.getFont(font).face.charToGlyph for char in text if char.isprintable())


def font_for_text(text: str, bold: bool = False, family: str = "Helvetica") -> str:
    register_fonts()
    if contains_cjk(text):
        return CJK_FONT
    font = FONT_FAMILIES[family][bold]
    return FALLBACK[font] if font in FALLBACK and not _has_glyphs(font, text) else font
