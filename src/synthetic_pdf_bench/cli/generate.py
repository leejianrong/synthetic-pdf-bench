from __future__ import annotations

import argparse
import json
from pathlib import Path

from synthetic_pdf_bench.evaluation.evaluator import (
    expected_prediction_shape,
    prediction_from_truth,
    write_evaluation_report,
)
from synthetic_pdf_bench.export.coco import write_coco
from synthetic_pdf_bench.generators.recipes import (
    default_recipe_path,
    recipe_variant_names,
)
from synthetic_pdf_bench.layout.flow_layout import build_scene_from_recipe_path
from synthetic_pdf_bench.markdown.writer import write_markdown
from synthetic_pdf_bench.quality import manifest_summary_stats, validate_generation
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


def _document_summary(output: Path, truth, recipe_path: Path, variant: str, quality: dict) -> dict:
    return {
        "doc_id": truth.doc_id,
        "output_dir": str(output),
        "pdf_path": str(output / "document.pdf"),
        "truth_json_path": str(output / "truth" / "document.json"),
        "truth_markdown_path": str(output / "truth" / "document.md"),
        "recipe_path": str(recipe_path),
        "recipe_variant": variant,
        "seed": truth.seed,
        "page_count": len(truth.pages),
        "block_count": len(truth.blocks),
        "table_count": len(truth.tables),
        "figure_count": len(truth.figures),
        "language_profile": truth.language_profile,
        "metadata": truth.metadata,
        "quality": quality,
    }


def generate(
    output: Path,
    seed: int = 123,
    dpi: int = 144,
    recipe_path: Path | None = None,
    variant: str = "standard",
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    _clear_generated_outputs(output)
    truth_dir = output / "truth"
    pages_dir = truth_dir / "pages"
    figures_dir = truth_dir / "figures"
    resolved_recipe_path = recipe_path or default_recipe_path()
    scene = build_scene_from_recipe_path(resolved_recipe_path, seed=seed, dpi=dpi, variant=variant)

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
    quality = validate_generation(output, truth, markdown)
    (truth_dir / "document.json").write_text(truth.model_dump_json(indent=2), encoding="utf-8")
    summary = _document_summary(output, truth, resolved_recipe_path, variant, quality)
    (truth_dir / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def generate_dataset(
    output_root: Path,
    count: int,
    seed_start: int = 1,
    dpi: int = 144,
    recipe_paths: list[Path] | None = None,
    variants: list[str] | None = None,
) -> dict:
    if count < 1:
        raise ValueError("count must be at least 1")
    recipes = recipe_paths or [default_recipe_path()]
    selected_variants = variants or ["standard"]
    output_root.mkdir(parents=True, exist_ok=True)
    documents = []
    for index in range(count):
        seed = seed_start + index
        recipe_path = recipes[index % len(recipes)]
        variant = selected_variants[index % len(selected_variants)]
        output = output_root / f"synthetic_{index + 1:06d}"
        documents.append(generate(output, seed=seed, dpi=dpi, recipe_path=recipe_path, variant=variant))
    manifest = {
        "dataset_id": output_root.name,
        "output_root": str(output_root),
        "count": count,
        "seed_start": seed_start,
        "dpi": dpi,
        "recipe_paths": [str(path) for path in recipes],
        "variants": selected_variants,
        "summary_stats": manifest_summary_stats(documents),
        "documents": documents,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a synthetic PDF benchmark document.")
    subparsers = parser.add_subparsers(dest="command")

    generate_parser = subparsers.add_parser("generate", help="Generate one document or a dataset.")
    _add_generation_args(generate_parser)

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate parser output against truth.")
    evaluate_parser.add_argument("--truth", type=Path, required=True)
    evaluate_parser.add_argument("--prediction", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path)

    dummy_parser = subparsers.add_parser("dummy-parse", help="Write a truth-copy prediction for evaluator tests.")
    dummy_parser.add_argument("--truth", type=Path, required=True)
    dummy_parser.add_argument("--prediction", type=Path, required=True)

    coco_parser = subparsers.add_parser("export-coco", help="Export layout annotations in COCO format.")
    coco_parser.add_argument("root", type=Path, help="Document or dataset directory.")
    coco_parser.add_argument("--output", type=Path, help="Defaults to <root>/coco.json.")

    shape_parser = subparsers.add_parser("prediction-shape", help="Print expected parser output shape.")
    shape_parser.add_argument("--output", type=Path)

    _add_generation_args(parser)
    return parser


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="Output directory for a single document.")
    parser.add_argument("--output-root", type=Path, help="Output root for dataset generation.")
    parser.add_argument("--count", type=int, default=1, help="Number of documents to generate in dataset mode.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--recipe", type=Path, action="append", default=None)
    parser.add_argument(
        "--variant",
        choices=recipe_variant_names(),
        default="standard",
        help="Recipe/layout variant for single-document generation.",
    )
    parser.add_argument(
        "--variants",
        choices=recipe_variant_names(),
        nargs="+",
        help="Variants to cycle through in dataset mode.",
    )


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "evaluate":
        report = write_evaluation_report(args.truth, args.prediction, args.output)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if args.command == "dummy-parse":
        prediction_from_truth(args.truth, args.prediction)
        return
    if args.command == "export-coco":
        print(write_coco(args.root, args.output))
        return
    if args.command == "prediction-shape":
        shape = expected_prediction_shape()
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(shape, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            print(json.dumps(shape, indent=2, ensure_ascii=False))
        return
    recipe_paths = args.recipe or [default_recipe_path()]
    if args.output_root is not None:
        generate_dataset(
            args.output_root,
            count=args.count,
            seed_start=args.seed_start,
            dpi=args.dpi,
            recipe_paths=recipe_paths,
            variants=args.variants or [args.variant],
        )
        return
    if args.output is None:
        raise SystemExit("--output is required unless --output-root is provided")
    generate(args.output, seed=args.seed, dpi=args.dpi, recipe_path=recipe_paths[0], variant=args.variant)


if __name__ == "__main__":
    main()
