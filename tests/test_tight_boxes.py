from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def test_text_boxes_hug_their_lines_horizontally(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=7, recipe_paths=RECIPES, variants=["structured"])
    blocks = [b for p in tmp_path.glob("*/truth/document.json") for pg in DocumentTruth.model_validate_json(p.read_text()).pages for b in pg.blocks if getattr(b, "lines", None)]
    assert blocks
    for b in blocks:
        assert abs(b.bbox_pt[0] - min(line.bbox_pt[0] for line in b.lines)) < 1e-6
        assert abs(b.bbox_pt[2] - max(line.bbox_pt[2] for line in b.lines)) < 1e-6
        assert b.bbox_px[0] == min(line.bbox_px[0] for line in b.lines) or abs(b.bbox_px[0] - min(line.bbox_px[0] for line in b.lines)) < 1e-3

    width = lambda kind: [b.bbox_pt[2] - b.bbox_pt[0] for b in blocks if b.type == kind]
    assert sum(width("heading")) / len(width("heading")) < 0.8 * sum(width("paragraph")) / len(width("paragraph"))  # headings no longer span the column


def test_pictures_are_narrower_than_the_column_and_vary(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=7, recipe_paths=RECIPES, variants=["structured"])
    figures = [b for p in tmp_path.glob("*/truth/document.json") for pg in DocumentTruth.model_validate_json(p.read_text()).pages for b in pg.blocks if b.type == "figure"]
    page_widths = {round(b.bbox_pt[2] - b.bbox_pt[0]) for b in figures}
    assert figures and len(page_widths) > 5  # sizes vary rather than all sitting at one inset
    assert sum(b.bbox_pt[2] - b.bbox_pt[0] for b in figures) / len(figures) < 0.7 * 460
