from pathlib import Path

from synthetic_pdf_bench.generators.recipes import load_recipe


def test_load_sea_recipe() -> None:
    recipe = load_recipe(Path("data/recipes/sea_historical_report_v1.json"))

    assert recipe.doc_id == "sea_historical_report_v1"
    assert len(recipe.sections) == 6
    assert sum(1 for section in recipe.sections for block in section.blocks if block.type == "table") == 6
    assert sum(1 for section in recipe.sections for block in section.blocks if block.type == "figure") == 6
