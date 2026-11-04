import json
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.export.tables import write_table_structure
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPE = Path("data/recipes/canonical/visual_benchmark_v1.json")


def _records(tmp_path: Path) -> tuple[list[dict], DocumentTruth]:
    generate(tmp_path / "doc", seed=5, recipe_path=RECIPE)
    out = write_table_structure(tmp_path / "doc")
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())
    return [json.loads(line) for line in out.read_text().splitlines()], truth


def test_one_record_per_table_segment_with_page_image(tmp_path: Path) -> None:
    records, truth = _records(tmp_path)
    assert len(records) == len(truth.tables)
    assert all((tmp_path / "doc" / r["filename"]).exists() for r in records)


def test_structure_tokens_carry_spans_and_cells_match_truth(tmp_path: Path) -> None:
    records, truth = _records(tmp_path)
    merged = next(r for r in records if r["table_id"] == "tbl_merged_cells")
    table = next(t for t in truth.tables if t.table_id == "tbl_merged_cells")
    tokens = merged["html"]["structure"]["tokens"]

    assert tokens[:3] == ["<thead>", "<tr>", "<td>"]
    assert ' colspan="2"' in tokens and ' rowspan="2"' in tokens
    assert tokens.count("<td>") + tokens.count("<td") == len(table.cells) == len(merged["html"]["cells"])
    first = merged["html"]["cells"][0]
    assert "".join(first["tokens"]) == table.cells[0].text
    assert first["bbox"] == table.cells[0].bbox_px
    assert merged["bbox"] == table.bbox_px
