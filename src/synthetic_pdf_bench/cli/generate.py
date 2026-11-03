from __future__ import annotations

import argparse
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from synthetic_pdf_bench.degrade import PROFILES, degrade_pages, write_scan_pdf
from synthetic_pdf_bench.evaluation.evaluator import (
    expected_prediction_shape,
    prediction_from_truth,
    write_evaluation_report,
)
from synthetic_pdf_bench.export.coco import write_coco
from synthetic_pdf_bench.export.tables import write_table_structure
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
from synthetic_pdf_bench.splits import SPLIT_BY, assign_splits, write_coco_splits


def _clear_generated_outputs(output: Path) -> None:
    files = [
        output / "document.pdf",
        output / "document_clean.pdf",
        output / "truth" / "document.json",
        output / "truth" / "document.md",
    ]
    for directory in [output / "truth" / "pages", output / "truth" / "figures"]:
        if directory.exists():
            files.extend(path for path in directory.iterdir() if path.is_file())
    for path in files:
        if path.exists():
            path.unlink()


def _document_summary(output: Path, truth, recipe_path: Path, variant: str, quality: dict, degrade: str) -> dict:
    return {
        "doc_id": truth.doc_id,
        "output_dir": str(output),
        "pdf_path": str(output / "document.pdf"),
        "truth_json_path": str(output / "truth" / "document.json"),
        "truth_markdown_path": str(output / "truth" / "document.md"),
        "recipe_path": str(recipe_path),
        "recipe_variant": variant,
        "degradation": degrade,
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
    degrade: str = "none",
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

    if degrade != "none":
        page_paths = [path for path, _, _ in rendered_pages]
        degrade_pages(scene, page_paths, degrade, seed)
        pdf_path.replace(output / "document_clean.pdf")
        write_scan_pdf(page_paths, scene.pages, pdf_path)

    markdown = write_markdown(scene.blocks_in_reading_order())
    truth_dir.mkdir(parents=True, exist_ok=True)
    (truth_dir / "document.md").write_text(markdown, encoding="utf-8")
    truth = scene.to_truth()
    quality = validate_generation(output, truth, markdown)
    (truth_dir / "document.json").write_text(truth.model_dump_json(indent=2), encoding="utf-8")
    summary = _document_summary(output, truth, resolved_recipe_path, variant, quality, degrade)
    (truth_dir / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def _generate_job(job: dict) -> dict:
    return generate(**job)


def generate_dataset(
    output_root: Path,
    count: int,
    seed_start: int = 1,
    dpi: int = 144,
    recipe_paths: list[Path] | None = None,
    variants: list[str] | None = None,
    degrade: str = "none",
    workers: int = 1,
    splits: dict[str, float] | None = None,
    split_by: str = "recipe",
) -> dict:
    if count < 1:
        raise ValueError("count must be at least 1")
    recipes = recipe_paths or [default_recipe_path()]
    selected_variants = variants or ["standard"]
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = [
        {
            "output": output_root / f"synthetic_{index + 1:06d}",
            "seed": seed_start + index,
            "dpi": dpi,
            "recipe_path": recipes[index % len(recipes)],
            "variant": selected_variants[index % len(selected_variants)],
            "degrade": degrade,
        }
        for index in range(count)
    ]
    if workers > 1:
        # spawn: matplotlib and PyMuPDF are not fork-safe
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            documents = list(pool.map(_generate_job, jobs))
    else:
        documents = [_generate_job(job) for job in jobs]
    split_ids = assign_splits(documents, splits, split_by, seed_start) if splits else None
    if split_ids:
        split_of = {doc_id: name for name, ids in split_ids.items() for doc_id in ids}
        for document in documents:
            document["split"] = split_of[document["doc_id"]]
        (output_root / "splits.json").write_text(
            json.dumps({"split_by": split_by, "ratios": splits, "splits": split_ids}, indent=2), encoding="utf-8"
        )
    manifest = {
        "dataset_id": output_root.name,
        "output_root": str(output_root),
        "count": count,
        "seed_start": seed_start,
        "dpi": dpi,
        "recipe_paths": [str(path) for path in recipes],
        "variants": selected_variants,
        "degradation": degrade,
        "splits": split_ids,
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

    tables_parser = subparsers.add_parser("export-tables", help="Export table structure (PubTabNet-style JSONL).")
    tables_parser.add_argument("root", type=Path, help="Document or dataset directory.")
    tables_parser.add_argument("--output", type=Path, help="Defaults to <root>/tables.jsonl.")

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
        "--degrade",
        choices=["none", *PROFILES],
        default="none",
        help="Scan degradation: page images are degraded, document.pdf becomes an image-only scan.",
    )
    parser.add_argument("--workers", type=int, default=1, help="Parallel processes in dataset mode.")
    parser.add_argument(
        "--splits",
        nargs="+",
        metavar="NAME=RATIO",
        help="Dataset mode: e.g. train=0.8 val=0.1 test=0.1. Writes splits.json; whole groups go to one split.",
    )
    parser.add_argument(
        "--split-by",
        choices=SPLIT_BY,
        default="recipe",
        help="Leakage group: recipe (same text source), template (same page layout), or document (can leak).",
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
        if args.output is None and (args.root / "splits.json").exists():
            print("\n".join(str(path) for path in write_coco_splits(args.root)))
        else:
            print(write_coco(args.root, args.output))
        return
    if args.command == "export-tables":
        print(write_table_structure(args.root, args.output))
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
            degrade=args.degrade,
            workers=args.workers,
            splits={name: float(ratio) for name, ratio in (item.split("=") for item in args.splits)} if args.splits else None,
            split_by=args.split_by,
        )
        return
    if args.output is None:
        raise SystemExit("--output is required unless --output-root is provided")
    generate(args.output, seed=args.seed, dpi=args.dpi, recipe_path=recipe_paths[0], variant=args.variant, degrade=args.degrade)


if __name__ == "__main__":
    main()
