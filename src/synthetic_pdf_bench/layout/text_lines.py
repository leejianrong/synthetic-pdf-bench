"""Line and word boxes for text blocks, computed once so the PDF is drawn from exactly the boxes the truth records."""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics

from synthetic_pdf_bench.layout.coordinates import pt_to_px_bbox
from synthetic_pdf_bench.render.fonts import contains_cjk, font_for_text
from synthetic_pdf_bench.schema.blocks import Block, TextLine, TextWord

ASCENT, DESCENT = 0.8, 0.22  # of the font size; a line box runs from baseline - descent to baseline + ascent


def wrap_tokens(text: str) -> list[str]:
    """Words (with their trailing space); every CJK character is its own token."""
    tokens: list[str] = []
    current = ""
    for char in text:
        if contains_cjk(char):
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
        elif char.isspace():
            current += char
            tokens.append(current)
            current = ""
        else:
            current += char
    if current:
        tokens.append(current)
    return tokens


def wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[list[str]]:
    """Greedy line breaking; each line is the list of its tokens."""
    lines: list[list[str]] = []
    current: list[str] = []
    for token in wrap_tokens(text):
        if current and pdfmetrics.stringWidth("".join(current + [token]).rstrip(), font_name, font_size) > max_width:
            lines.append(current)
            current = [token.lstrip()]
        else:
            current.append(token)
    if current:
        lines.append(current)
    return lines or [[""]]


def text_lines(block: Block, *, bold: bool, dpi: int, page_height_pt: float) -> list[TextLine]:
    """Lines that fit in the block box, top to bottom, with a box per line and per word."""
    font_size = block.metadata.get("font_size", 8)  # furniture (header/footer/page number) has no entry
    line_height = block.metadata.get("line_height", font_size * 1.25)
    x0, y0, x1, y1 = block.bbox_pt
    text = block.text or block.markdown
    marker, hang = block.metadata.get("marker"), block.metadata.get("hang", 0.0)  # list items: marker at the box edge, text hangs
    font = font_for_text(text, bold=bold, family=block.metadata.get("font_family", "Helvetica"))
    lines: list[TextLine] = []
    baseline = y1 - font_size
    for n, tokens in enumerate(wrap_text(text, font, font_size, x1 - x0 - hang)):
        if baseline < y0:
            break
        words, offset = [], hang
        if marker and n == 0:
            marker_box = [x0, baseline - DESCENT * font_size, x0 + pdfmetrics.stringWidth(marker, font, font_size), baseline + ASCENT * font_size]
            words.append(TextWord(text=marker, bbox_pt=marker_box, bbox_px=pt_to_px_bbox(marker_box, page_height_pt, dpi)))
        for token in tokens:
            width = pdfmetrics.stringWidth(token, font, font_size)
            word = token.strip()
            if word:
                left = x0 + offset + pdfmetrics.stringWidth(token[: len(token) - len(token.lstrip())], font, font_size)
                box = [left, baseline - DESCENT * font_size, left + pdfmetrics.stringWidth(word, font, font_size), baseline + ASCENT * font_size]
                words.append(TextWord(text=word, bbox_pt=box, bbox_px=pt_to_px_bbox(box, page_height_pt, dpi)))
            offset += width
        line_text = (f"{marker} " if marker and n == 0 else "") + "".join(tokens).strip()
        if words:
            box = [words[0].bbox_pt[0], baseline - DESCENT * font_size, words[-1].bbox_pt[2], baseline + ASCENT * font_size]
            lines.append(TextLine(text=line_text, bbox_pt=box, bbox_px=pt_to_px_bbox(box, page_height_pt, dpi), words=words))
        baseline -= line_height
    return lines
