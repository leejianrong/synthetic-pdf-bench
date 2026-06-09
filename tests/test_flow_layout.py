from pathlib import Path

from synthetic_pdf_bench.generators.recipes import apply_recipe_variant, load_recipe
from synthetic_pdf_bench.layout.flow_layout import build_scene_from_recipe
from synthetic_pdf_bench.schema.blocks import FigureBlock, TableBlock


def test_flow_layout_generates_multi_page_scene_with_repeated_furniture() -> None:
    recipe = load_recipe(Path("data/recipes/sea_historical_report_v1.json"))
    scene = build_scene_from_recipe(recipe, seed=123)
    truth = scene.to_truth()

    assert 3 <= len(truth.pages) <= 8
    assert truth.language_profile["primary"] == "en"
    assert truth.metadata["document_family"] == "synthetic_historical_research_report"
    assert len([block for block in truth.blocks if block.type == "header"]) == len(truth.pages)
    assert len([block for block in truth.blocks if block.type == "footer"]) == len(truth.pages)
    assert len([block for block in truth.blocks if block.type == "page_number"]) == len(truth.pages)
    assert any(isinstance(block, FigureBlock) and block.source_type == "raster" for block in truth.blocks)
    assert any(isinstance(block, FigureBlock) and block.source_type == "vector" for block in truth.blocks)


def test_flow_layout_records_table_cells() -> None:
    recipe = load_recipe(Path("data/recipes/sea_historical_report_v1.json"))
    scene = build_scene_from_recipe(recipe, seed=123)
    tables = [block for block in scene.blocks_in_reading_order() if isinstance(block, TableBlock)]

    assert tables
    for table in tables:
        assert len(table.cells) == len(table.matrix) * len(table.matrix[0])
        assert all(cell.bbox_pt for cell in table.cells)


def test_flow_layout_variant_changes_document_shape() -> None:
    recipe = load_recipe(Path("data/recipes/sea_historical_report_v1.json"))
    compact = build_scene_from_recipe(apply_recipe_variant(recipe, "compact", 1), seed=1, variant="compact").to_truth()
    spacious = build_scene_from_recipe(apply_recipe_variant(recipe, "spacious", 1), seed=1, variant="spacious").to_truth()

    assert len(compact.blocks) != len(spacious.blocks) or len(compact.pages) != len(spacious.pages)
    assert compact.metadata["recipe_variant"] == "compact"
    assert spacious.metadata["recipe_variant"] == "spacious"
