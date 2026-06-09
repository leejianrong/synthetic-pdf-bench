from __future__ import annotations

import argparse
from pathlib import Path

from synthetic_pdf_bench.generators.recipes import default_recipe_path
from synthetic_pdf_bench.layout.flow_layout import build_scene_from_recipe_path
from synthetic_pdf_bench.markdown.writer import write_markdown
from synthetic_pdf_bench.render.crops import crop_figures
from synthetic_pdf_bench.render.pymupdf_rasterizer import rasterize_pdf
from synthetic_pdf_bench.render.reportlab_renderer import ReportLabRenderer
from synthetic_pdf_bench.schema.blocks import FigureBlock


def _clear_generated_outputs(output: Path) -> None:
    files = [
        output / "document.pdf",
        output / "truth" / "document.json",
        output / "truth" / "document.md",
    ]
    for directory in [output / "truth" / "pages", output / "truth" / "figures"]:
        if directory.exists():
            files.extend(path for path in directory.iterdir() if path.is_file())
    for path in files:
        if path.exists():
            path.unlink()


def generate(output: Path, seed: int = 123, dpi: int = 144, recipe_path: Path | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _clear_generated_outputs(output)
    truth_dir = output / "truth"
    pages_dir = truth_dir / "pages"
    figures_dir = truth_dir / "figures"
    scene = build_scene_from_recipe_path(recipe_path or default_recipe_path(), seed=seed, dpi=dpi)

    pdf_path = output / "document.pdf"
    ReportLabRenderer(seed=seed).render(scene.pages, pdf_path)

    rendered_pages = rasterize_pdf(pdf_path, pages_dir, dpi=dpi)
    for page_index, (path, width_px, height_px) in enumerate(rendered_pages):
        scene.set_rendered_page(
            page_index,
            f"truth/pages/{path.name}",
            width_px=width_px,
            height_px=height_px,
        )

    figures = [block for block in scene.blocks_in_reading_order() if isinstance(block, FigureBlock)]
    crop_figures(figures, [path for path, _, _ in rendered_pages], figures_dir)

    markdown = write_markdown(scene.blocks_in_reading_order())
    truth_dir.mkdir(parents=True, exist_ok=True)
    (truth_dir / "document.md").write_text(markdown, encoding="utf-8")
    truth = scene.to_truth()
    (truth_dir / "document.json").write_text(truth.model_dump_json(indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a synthetic PDF benchmark document.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--recipe", type=Path, default=default_recipe_path())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    generate(args.output, seed=args.seed, dpi=args.dpi, recipe_path=args.recipe)


if __name__ == "__main__":
    main()
