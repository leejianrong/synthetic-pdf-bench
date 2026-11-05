from pathlib import Path

import pymupdf

from synthetic_pdf_bench.cli.generate import generate_dataset

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def _fills(root: Path) -> list[tuple]:
    fills = []
    for pdf_path in sorted(root.glob("*/document.pdf")):
        for page in pymupdf.open(pdf_path):
            big = [d["fill"] for d in page.get_drawings() if d.get("fill") and d["rect"].width >= page.rect.width - 1 and d["rect"].height >= page.rect.height - 1]
            fills.append(big[0] if big else None)
    return fills


def test_some_pages_have_a_tinted_background_and_most_stay_white(tmp_path: Path) -> None:
    generate_dataset(tmp_path / "a", count=7, recipe_paths=RECIPES, variants=["standard"])
    fills = _fills(tmp_path / "a")
    tinted = [f for f in fills if f is not None]

    assert 0.05 * len(fills) < len(tinted) < 0.5 * len(fills)
    assert all(min(f) > 0.8 for f in tinted)  # pale, so text stays legible


def test_background_is_deterministic(tmp_path: Path) -> None:
    generate_dataset(tmp_path / "a", count=3, recipe_paths=RECIPES[:3], variants=["standard"])
    generate_dataset(tmp_path / "b", count=3, recipe_paths=RECIPES[:3], variants=["standard"])

    assert _fills(tmp_path / "a") == _fills(tmp_path / "b")
