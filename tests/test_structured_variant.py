import re
from collections import Counter
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.export.coco import CATEGORIES, export_coco
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def _structured(tmp_path: Path, count: int = 7) -> Path:
    root = tmp_path / "ds"
    generate_dataset(root, count=count, recipe_paths=RECIPES, variants=["structured"])
    return root


def test_structured_variant_covers_all_eleven_classes(tmp_path: Path) -> None:
    coco = export_coco(_structured(tmp_path))
    names = {c["id"]: c["name"] for c in coco["categories"]}
    counts = Counter(names[a["category_id"]] for a in coco["annotations"])

    assert set(CATEGORIES) <= {name for name, n in counts.items() if n}


def test_lists_are_one_box_per_item_and_markdown_is_tight(tmp_path: Path) -> None:
    root = _structured(tmp_path)
    truths = [DocumentTruth.model_validate_json(p.read_text()) for p in root.glob("*/truth/document.json")]
    items = [b for t in truths for pg in t.pages for b in pg.blocks if b.type == "list_item"]
    assert items and all("\n" not in b.text for b in items)
    markdown = "\n".join(p.read_text() for p in root.glob("*/truth/document.md"))
    assert re.search(r"^- .*\n- ", markdown, re.MULTILINE) and not re.search(r"^- .*\n\n- ", markdown, re.MULTILINE)


def test_footnotes_sit_below_the_body_text_of_their_page(tmp_path: Path) -> None:
    root = _structured(tmp_path)
    checked = 0
    for path in root.glob("*/truth/document.json"):
        for page in DocumentTruth.model_validate_json(path.read_text()).pages:
            notes = [b for b in page.blocks if b.type == "footnote"]
            body = [b for b in page.blocks if b.type not in {"footnote", "header", "footer", "page_number"}]
            for note in notes:
                checked += 1
                assert all(note.bbox_pt[3] <= b.bbox_pt[1] + 1e-6 for b in body if _overlaps_x(note, b))
    assert checked


def _overlaps_x(a, b) -> bool:
    return a.bbox_pt[0] < b.bbox_pt[2] and b.bbox_pt[0] < a.bbox_pt[2]


def test_formula_block_carries_latex_markdown(tmp_path: Path) -> None:
    root = _structured(tmp_path)
    formulas = [b for p in root.glob("*/truth/document.json") for pg in DocumentTruth.model_validate_json(p.read_text()).pages for b in pg.blocks if b.type == "formula"]
    assert formulas and all(b.markdown == f"$${b.text}$$" for b in formulas)
