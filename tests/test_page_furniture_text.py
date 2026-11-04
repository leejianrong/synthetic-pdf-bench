from pathlib import Path

from synthetic_pdf_bench.generators.recipes import load_recipe
from synthetic_pdf_bench.layout.flow_layout import FlowLayoutPlanner

RECIPES = Path("data/recipes/canonical")


def _furniture(path: Path, **metadata) -> dict[str, str]:
    recipe = load_recipe(path)
    recipe.metadata.update(metadata)
    scene = FlowLayoutPlanner(seed=1).build_scene(recipe)
    return {b.type: b.text for page in scene.pages for b in page.blocks if b.type in {"header", "footer"}}


def test_header_defaults_to_the_recipe_title_before_the_colon() -> None:
    a = _furniture(RECIPES / "indonesia_colonial_nationalist_origins_v1.json")
    b = _furniture(RECIPES / "singapore_history_1900_2020s_v1.json")
    assert (a["header"], b["header"]) == ("Indonesia", "Singapore")


def test_header_and_footer_can_be_set_in_the_recipe() -> None:
    got = _furniture(RECIPES / "sea_historical_report_v1.json", header_text="Annual Review", footer_text="Confidential")
    assert got == {"header": "Annual Review", "footer": "Confidential"}
