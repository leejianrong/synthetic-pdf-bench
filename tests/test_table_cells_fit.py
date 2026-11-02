from pathlib import Path

import fitz
import pytest

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.schema.truth import DocumentTruth

CASES = [(v, 5) for v in ("standard", "compact", "two_column", "table_heavy")]
CASES += [("random", seed) for seed in range(1, 9)]


@pytest.mark.parametrize(("variant", "seed"), CASES)
def test_every_word_of_every_cell_is_drawn_inside_its_cell(tmp_path: Path, variant: str, seed: int) -> None:
    generate(tmp_path / "doc", seed=seed, variant=variant)
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())
    pdf = fitz.open(tmp_path / "doc/document.pdf")

    clipped = []
    for table in truth.tables:
        page = truth.pages[table.page_index]
        words = pdf[table.page_index].get_text("words")
        for cell in table.cells:
            x0, y0, x1, y1 = cell.bbox_pt
            top, bottom = page.height_pt - y1, page.height_pt - y0
            inside = [w for w in words if x0 - 1 <= w[0] and w[2] <= x1 + 1 and top <= (w[1] + w[3]) / 2 <= bottom]
            if len(inside) < len(cell.text.split()):
                clipped.append(cell.cell_id)

    assert not clipped
