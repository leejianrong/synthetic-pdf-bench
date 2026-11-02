from pathlib import Path

from synthetic_pdf_bench.generators.recipes import (
    DocumentRecipe,
    apply_recipe_variant,
    load_recipe,
)
from synthetic_pdf_bench.layout.flow_layout import (
    FlowLayoutPlanner,
    build_scene_from_recipe,
)
from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock


def test_flow_layout_generates_multi_page_scene_with_repeated_furniture() -> None:
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))
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
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))
    scene = build_scene_from_recipe(recipe, seed=123)
    tables = [block for block in scene.blocks_in_reading_order() if isinstance(block, TableBlock)]

    assert tables
    for table in tables:
        assert len(table.cells) == len(table.matrix) * len(table.matrix[0])
        assert all(cell.bbox_pt for cell in table.cells)


def test_flow_layout_variant_changes_document_shape() -> None:
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))
    compact = build_scene_from_recipe(apply_recipe_variant(recipe, "compact", 1), seed=1, variant="compact").to_truth()
    spacious = build_scene_from_recipe(apply_recipe_variant(recipe, "spacious", 1), seed=1, variant="spacious").to_truth()

    assert len(compact.blocks) != len(spacious.blocks) or len(compact.pages) != len(spacious.pages)
    assert compact.metadata["recipe_variant"] == "compact"
    assert spacious.metadata["recipe_variant"] == "spacious"


def test_two_column_layout_uses_distinct_columns() -> None:
    recipe = load_recipe(Path("data/recipes/canonical/sea_historical_report_v1.json"))
    truth = build_scene_from_recipe(
        apply_recipe_variant(recipe, "two_column", 3), seed=3, variant="two_column"
    ).to_truth()
    paragraph_x0s = sorted({round(block.bbox_pt[0]) for block in truth.blocks if block.type == "paragraph"})

    assert len(paragraph_x0s) >= 2
    assert truth.metadata["recipe_variant"] == "two_column"


def test_flow_layout_supports_lists_footnotes_references_and_caption_before() -> None:
    recipe = DocumentRecipe.model_validate(
        {
            "doc_id": "layout_features",
            "title": "Layout Features",
            "sections": [
                {
                    "heading": "Lists and Notes",
                    "page_break_before": True,
                    "blocks": [
                        {"type": "list", "items": ["First point", "Second point"], "ordered": False},
                        {"type": "footnote", "marker": "1.", "text": "A layout footnote."},
                        {"type": "reference", "text": "Reference: Synthetic source metadata."},
                        {
                            "type": "figure",
                            "figure_id": "fig_caption_before",
                            "kind": "flow_diagram",
                            "source_type": "vector",
                            "title": "Caption Before",
                            "caption": "Caption appears before the figure.",
                            "caption_position": "before",
                            "data": {
                                "nodes": [{"node_id": "a", "label": "A"}, {"node_id": "b", "label": "B"}],
                                "edges": [{"from": "a", "to": "b"}],
                            },
                        },
                    ],
                }
            ],
        }
    )

    truth = build_scene_from_recipe(recipe, seed=10).to_truth()
    blocks = truth.blocks
    figure = next(block for block in blocks if isinstance(block, FigureBlock) and block.figure_id == "fig_caption_before")
    caption = next(block for block in blocks if block.block_id == figure.caption_block_id)

    assert any(block.type == "list" and block.markdown.startswith("- First") for block in blocks)
    assert any(block.type == "footnote" for block in blocks)
    assert any(block.type == "reference" for block in blocks)
    assert caption.reading_order < figure.reading_order


def test_flow_layout_splits_long_tables() -> None:
    rows = [["Metric", "Value"]] + [[f"Row {index}", str(index)] for index in range(1, 80)]
    recipe = DocumentRecipe.model_validate(
        {
            "doc_id": "long_table",
            "title": "Long Table",
            "sections": [
                {
                    "heading": "Split Table",
                    "blocks": [
                        {
                            "type": "table",
                            "table_id": "tbl_long",
                            "caption": "A table that must split across pages.",
                            "matrix": rows,
                        }
                    ],
                }
            ],
        }
    )

    truth = build_scene_from_recipe(recipe, seed=11).to_truth()
    tables = [block for block in truth.blocks if isinstance(block, TableBlock)]

    assert len(tables) > 1
    assert all(table.metadata["parent_table_id"] == "tbl_long" for table in tables)
    assert any(table.table_id.startswith("tbl_long_part_") for table in tables)


def test_layout_validation_detects_overlapping_content_blocks() -> None:
    planner = FlowLayoutPlanner()
    scene = planner.scene = SceneGraph(doc_id="bad", seed=1)
    scene.add_page(200, 200)
    scene.add_block(
        Block(block_id="b1", type="paragraph", page_index=0, reading_order=1, bbox_pt=[10, 10, 100, 100])
    )
    scene.add_block(
        Block(block_id="b2", type="paragraph", page_index=0, reading_order=2, bbox_pt=[50, 50, 120, 120])
    )

    try:
        planner.validate_layout()
    except ValueError as exc:
        assert "overlap" in str(exc)
        return
    raise AssertionError("overlapping blocks should fail layout validation")
