from __future__ import annotations

from pathlib import Path
from statistics import mean

from PIL import Image, ImageStat

from synthetic_pdf_bench.schema.blocks import FigureBlock, TableBlock
from synthetic_pdf_bench.schema.truth import DocumentTruth


def validate_generation(output: Path, truth: DocumentTruth, markdown: str) -> dict:
    checks: list[dict] = []
    _check_blocks_have_bboxes(truth, checks)
    _check_markdown_spans(truth, markdown, checks)
    _check_figure_captions(truth, checks)
    _check_table_cells_inside_tables(truth, checks)
    _check_no_content_overlap(truth, checks)
    _check_page_images(output, truth, checks)
    _check_figure_crops(output, truth, checks)
    failed = [check for check in checks if not check["passed"]]
    if failed:
        details = "; ".join(check["name"] for check in failed)
        raise ValueError(f"generation quality validation failed: {details}")
    return {
        "passed": True,
        "check_count": len(checks),
        "checks": checks,
        "visual_smoke": {
            "page_images_checked": len(truth.pages),
            "figure_crops_checked": len(truth.figures),
        },
    }


def manifest_summary_stats(document_summaries: list[dict]) -> dict:
    if not document_summaries:
        return {
            "document_count": 0,
            "page_count": {"min": 0, "max": 0, "mean": 0},
            "block_count": {"min": 0, "max": 0, "mean": 0},
            "table_count": {"min": 0, "max": 0, "mean": 0},
            "figure_count": {"min": 0, "max": 0, "mean": 0},
            "variants": {},
        }
    return {
        "document_count": len(document_summaries),
        "page_count": _stats([doc["page_count"] for doc in document_summaries]),
        "block_count": _stats([doc["block_count"] for doc in document_summaries]),
        "table_count": _stats([doc["table_count"] for doc in document_summaries]),
        "figure_count": _stats([doc["figure_count"] for doc in document_summaries]),
        "variants": _counts(doc["recipe_variant"] for doc in document_summaries),
    }


def _stats(values: list[int]) -> dict:
    return {"min": min(values), "max": max(values), "mean": mean(values)}


def _counts(values) -> dict:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _check_blocks_have_bboxes(truth: DocumentTruth, checks: list[dict]) -> None:
    missing = [block.block_id for block in truth.blocks if not block.bbox_pt or len(block.bbox_pt) != 4]
    checks.append({"name": "all_blocks_have_bbox", "passed": not missing, "details": {"missing": missing}})


def _check_markdown_spans(truth: DocumentTruth, markdown: str, checks: list[dict]) -> None:
    failures = []
    for block in truth.blocks:
        if not block.include_in_markdown:
            continue
        if block.markdown_span is None:
            failures.append({"block_id": block.block_id, "reason": "missing_span"})
            continue
        start, end = block.markdown_span
        if start < 0 or end < start or end > len(markdown):
            failures.append({"block_id": block.block_id, "reason": "out_of_bounds"})
            continue
        if block.markdown and markdown[start:end] != block.markdown:
            failures.append({"block_id": block.block_id, "reason": "span_text_mismatch"})
    checks.append({"name": "included_markdown_blocks_have_valid_spans", "passed": not failures, "details": failures})


def _check_figure_captions(truth: DocumentTruth, checks: list[dict]) -> None:
    block_ids = {block.block_id for block in truth.blocks}
    failures = [
        figure.figure_id
        for figure in truth.figures
        if figure.caption_block_id is not None and figure.caption_block_id not in block_ids
    ]
    checks.append({"name": "figure_captions_resolve", "passed": not failures, "details": {"figures": failures}})


def _check_table_cells_inside_tables(truth: DocumentTruth, checks: list[dict]) -> None:
    failures = []
    for table in truth.tables:
        tx0, ty0, tx1, ty1 = table.bbox_pt
        for cell in table.cells:
            cx0, cy0, cx1, cy1 = cell.bbox_pt
            if cx0 < tx0 or cy0 < ty0 or cx1 > tx1 or cy1 > ty1:
                failures.append({"table_id": table.table_id, "cell_id": cell.cell_id})
    checks.append({"name": "table_cells_inside_table_bbox", "passed": not failures, "details": failures})


def _check_no_content_overlap(truth: DocumentTruth, checks: list[dict]) -> None:
    failures = []
    for page in truth.pages:
        blocks = [block for block in page.blocks if block.type not in {"header", "footer", "page_number"}]
        for index, block_a in enumerate(blocks):
            for block_b in blocks[index + 1 :]:
                if _boxes_overlap(block_a.bbox_pt, block_b.bbox_pt):
                    failures.append({"page_index": page.page_index, "a": block_a.block_id, "b": block_b.block_id})
    checks.append({"name": "no_overlapping_content_blocks", "passed": not failures, "details": failures})


def _check_page_images(output: Path, truth: DocumentTruth, checks: list[dict]) -> None:
    failures = []
    for page in truth.pages:
        if page.rendered_image is None:
            failures.append({"page_index": page.page_index, "reason": "missing_rendered_image"})
            continue
        path = output / page.rendered_image.image_path
        if not path.is_file():
            failures.append({"page_index": page.page_index, "reason": "missing_file"})
            continue
        if _image_is_blank(path):
            failures.append({"page_index": page.page_index, "reason": "blank_image"})
    checks.append({"name": "page_images_exist_and_nonblank", "passed": not failures, "details": failures})


def _check_figure_crops(output: Path, truth: DocumentTruth, checks: list[dict]) -> None:
    failures = []
    for figure in truth.figures:
        if not figure.png_path:
            failures.append({"figure_id": figure.figure_id, "reason": "missing_png_path"})
            continue
        path = output / figure.png_path
        if not path.is_file():
            failures.append({"figure_id": figure.figure_id, "reason": "missing_file"})
            continue
        if _image_is_blank(path):
            failures.append({"figure_id": figure.figure_id, "reason": "blank_image"})
    checks.append({"name": "figure_crops_exist_and_nonblank", "passed": not failures, "details": failures})


def _image_is_blank(path: Path) -> bool:
    with Image.open(path) as image:
        stat = ImageStat.Stat(image.convert("L"))
        return stat.stddev[0] < 1.0


def _boxes_overlap(box_a: list[float], box_b: list[float]) -> bool:
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    return max(ax0, bx0) < min(ax1, bx1) and max(ay0, by0) < min(ay1, by1)
