from pathlib import Path

from synthetic_pdf_bench.generators.recipes import (
    apply_recipe_variant,
    load_recipe,
    recipe_variant_names,
)


def test_load_sea_recipe() -> None:
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))

    assert recipe.doc_id == "sea_historical_report_v1"
    assert len(recipe.sections) == 6
    assert sum(1 for section in recipe.sections for block in section.blocks if block.type == "table") == 6
    assert sum(1 for section in recipe.sections for block in section.blocks if block.type == "figure") == 6


def test_apply_recipe_variants() -> None:
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))

    for variant in recipe_variant_names():
        varied = apply_recipe_variant(recipe, variant=variant, seed=7)
        assert varied.doc_id.endswith(f"{variant}_000007")
        assert varied.metadata["recipe_variant"] == variant
        assert varied.sections

    compact = apply_recipe_variant(recipe, variant="compact", seed=7)
    standard = apply_recipe_variant(recipe, variant="standard", seed=7)
    compact_blocks = sum(len(section.blocks) for section in compact.sections)
    standard_blocks = sum(len(section.blocks) for section in standard.sections)
    assert compact_blocks < standard_blocks
