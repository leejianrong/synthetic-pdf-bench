from pathlib import Path

import pymupdf

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.schema.truth import DocumentTruth


def _truth(path: Path) -> DocumentTruth:
    return DocumentTruth.model_validate_json((path / "truth" / "document.json").read_text())


def _text_blocks(truth: DocumentTruth):
    return [b for p in truth.pages for b in p.blocks if b.lines]


def test_lines_and_words_are_in_the_truth_and_inside_their_block(tmp_path: Path) -> None:
    generate(tmp_path / "d", seed=123)
    blocks = _text_blocks(_truth(tmp_path / "d"))

    assert len(blocks) > 20
    for block in blocks:
        for line in block.lines:
            assert "".join(w.text for w in line.words) == line.text.replace(" ", "")  # CJK characters are one word each
            for word in line.words:
                assert block.bbox_pt[0] - 0.5 <= word.bbox_pt[0] and word.bbox_pt[2] <= block.bbox_pt[2] + 0.5
                assert block.bbox_pt[1] - 0.5 <= word.bbox_pt[1] and word.bbox_pt[3] <= block.bbox_pt[3] + 0.5


def test_word_boxes_agree_with_the_pdf_text_layer(tmp_path: Path) -> None:
    generate(tmp_path / "d", seed=123)
    truth = _truth(tmp_path / "d")
    doc = pymupdf.open(tmp_path / "d" / "document.pdf")
    hits = total = 0
    for page in truth.pages:
        found = [(w[4], (w[0] + w[2]) / 2, (w[1] + w[3]) / 2) for w in doc[page.page_index].get_text("words")]
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    x0, y0, x1, y1 = word.bbox_pt
                    total += 1
                    # PyMuPDF y runs down from the top; ours runs up from the bottom
                    hits += any(t == word.text and x0 <= cx <= x1 and page.height_pt - y1 <= cy <= page.height_pt - y0 for t, cx, cy in found)
    assert total > 500 and hits / total > 0.98


def test_degraded_word_boxes_follow_the_page(tmp_path: Path) -> None:
    generate(tmp_path / "clean", seed=123)
    generate(tmp_path / "scan", seed=123, degrade="heavy_scan")
    clean, scan = _text_blocks(_truth(tmp_path / "clean")), _text_blocks(_truth(tmp_path / "scan"))

    moved = [(a.bbox_px, b.bbox_px) for a_block, b_block in zip(clean, scan, strict=True) for a, b in zip(a_block.lines[0].words, b_block.lines[0].words, strict=True)]
    assert any(a != b for a, b in moved)
    for block in scan:  # each word stays inside its block's degraded box, give or take the rounding of the skew hull
        for word in (w for line in block.lines for w in line.words):
            assert block.bbox_px[0] - 3 <= word.bbox_px[0] and word.bbox_px[2] <= block.bbox_px[2] + 3
