from pathlib import Path

from PIL import Image

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.generators.figures import make_matplotlib_figure
from synthetic_pdf_bench.generators.recipes import load_recipe
from synthetic_pdf_bench.generators.tables import make_table_variant_matrix, table_variant_names
from synthetic_pdf_bench.layout.flow_layout import build_scene_from_recipe
from synthetic_pdf_bench.schema.blocks import FigureBlock, TableBlock


def test_matplotlib_chart_backend_generates_png() -> None:
    path = make_matplotlib_figure(
        "heatmap",
        {"backend": "matplotlib", "matrix": [[0.1, 0.9], [0.6, 0.3]]},
        seed=12,
        figure_id="fig_test_heatmap",
    )

    assert path.is_file()
    with Image.open(path) as image:
        assert image.size[0] > 100
        assert image.size[1] > 100


def test_table_variant_matrices_are_valid() -> None:
    for variant in table_variant_names():
        matrix, merged_cells = make_table_variant_matrix(variant, seed=5)
        widths = {len(row) for row in matrix}
        assert len(matrix) >= 2
        assert len(widths) == 1
        if variant == "merged_cell_approximation":
            assert merged_cells[0]["colspan"] > 1


def test_visual_benchmark_recipe_contains_chart_and_table_variants() -> None:
    recipe = load_recipe(Path("data/recipes/visual_benchmark_v1.json"))
    scene = build_scene_from_recipe(recipe, seed=5)
    truth = scene.to_truth()
    figures = [block for block in truth.blocks if isinstance(block, FigureBlock)]
    tables = [block for block in truth.blocks if isinstance(block, TableBlock)]

    assert {"bar_chart", "line_chart", "stacked_bar", "timeline", "scatter_plot", "heatmap"}.issubset(
        {figure.kind for figure in figures}
    )
    assert {"narrow", "wide", "numeric", "multilingual", "wrapped_cell_text", "merged_cell_approximation"}.issubset(
        {table.metadata.get("table_variant") for table in tables}
    )
    assert any(table.metadata.get("parent_table_id") == "tbl_multi_page" for table in tables)
    merged_table = next(table for table in tables if table.table_id == "tbl_merged_approx")
    assert any(cell.colspan > 1 for cell in merged_table.cells)


def test_visual_benchmark_generation_outputs_chart_crops(tmp_path: Path) -> None:
    output = tmp_path / "visual"
    summary = generate(output, seed=77, recipe_path=Path("data/recipes/visual_benchmark_v1.json"))

    assert summary["figure_count"] >= 6
    assert summary["table_count"] >= 7
    assert (output / "truth" / "figures" / "fig_bar_chart.png").is_file()
    assert (output / "truth" / "figures" / "fig_heatmap.png").is_file()
