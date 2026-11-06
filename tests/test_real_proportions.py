from pathlib import Path
from statistics import median

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.layout.flow_layout import random_style
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def test_single_column_pages_leave_wide_margins_like_real_text_blocks() -> None:
    styles = [random_style(seed) for seed in range(400)]
    single = [s for s in styles if s.columns == 1]
    widths = [(s.page_size[0] - s.margin_left - s.margin_right) / s.page_size[0] for s in single]
    assert single and sum(widths) / len(widths) < 0.76  # was 0.79; narrower than 0.72 (SYN-38) cost page density, and SYN-38 showed width alone does not move the score
    assert min(widths) > 0.45  # still room for a readable line


def test_pictures_are_a_small_share_of_the_page(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=14, recipe_paths=RECIPES, variants=["structured"])
    shares = []
    for path in tmp_path.glob("*/truth/document.json"):
        truth = DocumentTruth.model_validate_json(path.read_text())
        for page in truth.pages:
            shares += [(b.bbox_pt[2] - b.bbox_pt[0]) * (b.bbox_pt[3] - b.bbox_pt[1]) / (page.width_pt * page.height_pt) for b in page.blocks if b.type == "figure"]
    assert len(shares) > 10
    assert median(shares) < 0.06  # DocLayNet median is 0.028; the generator gave 0.08
