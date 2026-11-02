from pathlib import Path

import fitz
import pytest

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.schema.truth import DocumentTruth

TEXT_TYPES = {"title", "heading", "paragraph", "list", "caption", "footnote", "reference"}


CASES = [(v, 5) for v in ("standard", "compact", "spacious", "two_column", "text_heavy")]
CASES += [("random", seed) for seed in range(1, 13)]


@pytest.mark.parametrize(("variant", "seed"), CASES)
def test_rendered_text_fits_inside_its_bbox(tmp_path: Path, variant: str, seed: int) -> None:
    generate(tmp_path / "doc", seed=seed, variant=variant)
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())
    pdf = fitz.open(tmp_path / "doc/document.pdf")

    overflowing = []
    for page in truth.pages:
        words = pdf[page.page_index].get_text("words")
        for block in page.blocks:
            if block.type not in TEXT_TYPES:
                continue
            x0, y0, x1, y1 = block.bbox_pt
            top, bottom = page.height_pt - y1, page.height_pt - y0  # PDF y-up -> fitz y-down
            # Word boxes carry font-metric padding, so test each word's center, not its edges.
            inside = [
                w for w in words if x0 - 1 <= w[0] and w[2] <= x1 + 1 and top <= (w[1] + w[3]) / 2 <= bottom
            ]
            if len(inside) < len(block.text.split()):
                overflowing.append(block.block_id)

    assert not overflowing
