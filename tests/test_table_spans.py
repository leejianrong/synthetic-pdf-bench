from pathlib import Path

import pytest
from pydantic import ValidationError

from synthetic_pdf_bench.generators.recipes import DocumentRecipe, SectionRecipe, TableRecipe, load_recipe
from synthetic_pdf_bench.layout.flow_layout import build_scene_from_recipe
from synthetic_pdf_bench.schema import TableBlock


def _merged_table(seed: int = 5) -> TableBlock:
    recipe = load_recipe(Path("data/recipes/canonical/visual_benchmark_v1.json"))
    truth = build_scene_from_recipe(recipe, seed=seed).to_truth()
    return next(b for b in truth.blocks if isinstance(b, TableBlock) and b.table_id == "tbl_merged_cells")


def test_spans_are_real_cells_not_metadata() -> None:
    table = _merged_table()
    by_pos = {(c.row, c.col): c for c in table.cells}

    wide, tall = by_pos[(2, 1)], by_pos[(2, 0)]
    assert (wide.rowspan, wide.colspan) == (1, 2)
    assert (tall.rowspan, tall.colspan) == (2, 1)
    assert (2, 2) not in by_pos and (3, 0) not in by_pos  # covered positions have no cell of their own

    neighbour, below = by_pos[(2, 3)], by_pos[(3, 1)]
    assert wide.bbox_pt[2] == pytest.approx(by_pos[(2, 3)].bbox_pt[0])
    assert wide.bbox_pt[0] == pytest.approx(below.bbox_pt[0])
    assert tall.bbox_pt[1] == pytest.approx(below.bbox_pt[1])
    assert tall.bbox_pt[3] == pytest.approx(neighbour.bbox_pt[3])


def test_cell_boxes_do_not_overlap() -> None:
    cells = _merged_table().cells
    for i, a in enumerate(cells):
        for b in cells[i + 1 :]:
            overlap_x = min(a.bbox_pt[2], b.bbox_pt[2]) - max(a.bbox_pt[0], b.bbox_pt[0])
            overlap_y = min(a.bbox_pt[3], b.bbox_pt[3]) - max(a.bbox_pt[1], b.bbox_pt[1])
            assert overlap_x <= 0.01 or overlap_y <= 0.01, (a.cell_id, b.cell_id)


def test_html_carries_spans() -> None:
    html = _merged_table().html
    assert html.count('colspan="2"') == 1
    assert html.count('rowspan="2"') == 1


def test_invalid_spans_are_rejected() -> None:
    base = {"type": "table", "table_id": "t", "matrix": [["a", "b"], ["c", "d"], ["e", "f"]]}
    for bad in (
        {"row": 1, "col": 1, "colspan": 2},  # past the right edge
        {"row": 2, "col": 0, "rowspan": 2},  # past the bottom
        {"row": 0, "col": 0, "rowspan": 2},  # crosses the repeated header row
    ):
        with pytest.raises(ValidationError):
            TableRecipe.model_validate({**base, "merged_cells": [bad]})
    overlap = [{"row": 1, "col": 0, "colspan": 2}, {"row": 1, "col": 1, "rowspan": 2}]
    with pytest.raises(ValidationError):
        TableRecipe.model_validate({**base, "merged_cells": overlap})


def test_row_spans_are_never_split_across_segments() -> None:
    matrix = [["k", "v"]] + [[f"g{i // 2}", f"v{i}"] for i in range(80)]
    recipe = TableRecipe(
        type="table",
        table_id="t",
        matrix=matrix,
        merged_cells=[{"row": r, "col": 0, "rowspan": 2} for r in range(1, 81, 2)],
    )
    doc = DocumentRecipe(doc_id="d", title="T", sections=[SectionRecipe(heading="S", blocks=[recipe])])
    truth = build_scene_from_recipe(doc, seed=1).to_truth()
    segments = [b for b in truth.blocks if isinstance(b, TableBlock)]
    assert len(segments) > 1
    for seg in segments:
        rows = len(seg.matrix)
        assert all(c.row + c.rowspan <= rows for c in seg.cells)
        assert sum(c.rowspan > 1 for c in seg.cells) == (rows - 1) // 2
