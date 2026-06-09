from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from synthetic_pdf_bench.evaluation.normalize_markdown import normalize_markdown
from synthetic_pdf_bench.evaluation.prediction import PredictionDocument
from synthetic_pdf_bench.evaluation.table_metrics import table_exact_match
from synthetic_pdf_bench.evaluation.text_metrics import token_f1
from synthetic_pdf_bench.layout.coordinates import bbox_iou
from synthetic_pdf_bench.schema.blocks import FigureBlock, TableBlock
from synthetic_pdf_bench.schema.truth import DocumentTruth


def evaluate_prediction(truth_dir: Path, prediction_dir: Path) -> dict:
    truth = _load_truth(truth_dir)
    prediction = _load_prediction(prediction_dir)
    truth_markdown = (truth_dir / "document.md").read_text(encoding="utf-8")
    predicted_markdown = prediction.markdown

    markdown_scores = {
        "normalized_exact_match": normalize_markdown(predicted_markdown) == normalize_markdown(truth_markdown),
        **token_f1(predicted_markdown, truth_markdown),
    }
    table_scores = _table_scores(truth, prediction)
    figure_scores = _figure_scores(truth, prediction)
    block_scores = _block_scores(truth, prediction)
    return {
        "truth_dir": str(truth_dir),
        "prediction_dir": str(prediction_dir),
        "doc_id": truth.doc_id,
        "markdown": markdown_scores,
        "blocks": block_scores,
        "tables": table_scores,
        "figures": figure_scores,
        "overall": {
            "markdown_token_f1": markdown_scores["f1"],
            "mean_block_bbox_iou": block_scores["mean_bbox_iou"],
            "table_exact_match_rate": table_scores["exact_match_rate"],
            "figure_count_match": figure_scores["count_match"],
            "figure_markdown_ref_match_rate": figure_scores["markdown_ref_match_rate"],
        },
    }


def write_evaluation_report(truth_dir: Path, prediction_dir: Path, output_path: Path | None = None) -> dict:
    report = evaluate_prediction(truth_dir, prediction_dir)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _load_truth(truth_dir: Path) -> DocumentTruth:
    raw = json.loads((truth_dir / "document.json").read_text(encoding="utf-8"))
    try:
        return DocumentTruth.model_validate(raw)
    except Exception:
        return DocumentTruth.model_validate(_repair_legacy_truth_blocks(raw))


def _repair_legacy_truth_blocks(raw: dict) -> dict:
    detailed_by_block_id = {
        item["block_id"]: item
        for item in [*raw.get("tables", []), *raw.get("figures", [])]
        if "block_id" in item
    }
    raw = dict(raw)
    raw["blocks"] = [detailed_by_block_id.get(block.get("block_id"), block) for block in raw.get("blocks", [])]
    pages = []
    for page in raw.get("pages", []):
        page = dict(page)
        page["blocks"] = [detailed_by_block_id.get(block.get("block_id"), block) for block in page.get("blocks", [])]
        pages.append(page)
    raw["pages"] = pages
    return raw


def _load_prediction(prediction_dir: Path) -> PredictionDocument:
    prediction_json = prediction_dir / "prediction.json"
    markdown_path = prediction_dir / "document.md"
    if prediction_json.exists():
        prediction = PredictionDocument.model_validate_json(prediction_json.read_text(encoding="utf-8"))
        if not prediction.markdown and markdown_path.exists():
            prediction.markdown = markdown_path.read_text(encoding="utf-8")
        return prediction
    if markdown_path.exists():
        return PredictionDocument(markdown=markdown_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"prediction directory must contain prediction.json or document.md: {prediction_dir}")


def _block_scores(truth: DocumentTruth, prediction: PredictionDocument) -> dict:
    predicted_by_id = {block.block_id: block for block in prediction.blocks}
    ious = []
    matched = 0
    for truth_block in truth.blocks:
        predicted = predicted_by_id.get(truth_block.block_id)
        if predicted is None or predicted.bbox_pt is None:
            continue
        matched += 1
        ious.append(bbox_iou(truth_block.bbox_pt, predicted.bbox_pt))
    return {
        "truth_count": len(truth.blocks),
        "predicted_count": len(prediction.blocks),
        "matched_by_id": matched,
        "mean_bbox_iou": mean(ious) if ious else 0.0,
    }


def _table_scores(truth: DocumentTruth, prediction: PredictionDocument) -> dict:
    truth_tables = {table.table_id: table for table in truth.tables}
    predicted_tables = {table.table_id: table for table in prediction.tables}
    matches = 0
    for table_id, truth_table in truth_tables.items():
        predicted = predicted_tables.get(table_id)
        if predicted is not None and table_exact_match(predicted.matrix, truth_table.matrix):
            matches += 1
    truth_count = len(truth_tables)
    return {
        "truth_count": truth_count,
        "predicted_count": len(predicted_tables),
        "exact_matches": matches,
        "exact_match_rate": matches / truth_count if truth_count else 1.0,
    }


def _figure_scores(truth: DocumentTruth, prediction: PredictionDocument) -> dict:
    truth_figures = {figure.figure_id: figure for figure in truth.figures}
    predicted_figures = {figure.figure_id: figure for figure in prediction.figures}
    bbox_ious = []
    markdown_ref_matches = 0
    for figure_id, truth_figure in truth_figures.items():
        predicted = predicted_figures.get(figure_id)
        if predicted is None:
            continue
        if predicted.bbox_pt is not None:
            bbox_ious.append(bbox_iou(truth_figure.bbox_pt, predicted.bbox_pt))
        if predicted.markdown_ref == truth_figure.markdown_ref:
            markdown_ref_matches += 1
    truth_count = len(truth_figures)
    return {
        "truth_count": truth_count,
        "predicted_count": len(predicted_figures),
        "count_match": len(predicted_figures) == truth_count,
        "mean_bbox_iou": mean(bbox_ious) if bbox_ious else 0.0,
        "markdown_ref_matches": markdown_ref_matches,
        "markdown_ref_match_rate": markdown_ref_matches / truth_count if truth_count else 1.0,
    }


def expected_prediction_shape() -> dict:
    return {
        "prediction_dir": {
            "document.md": "Predicted Markdown text. Optional if prediction.json contains markdown.",
            "prediction.json": {
                "doc_id": "optional document identifier",
                "markdown": "predicted Markdown text",
                "blocks": [
                    {
                        "block_id": "truth-compatible block id when available",
                        "type": "paragraph",
                        "page_index": 0,
                        "bbox_pt": [72, 100, 540, 130],
                        "text": "optional extracted text",
                        "markdown": "optional block markdown",
                        "metadata": {},
                    }
                ],
                "tables": [{"table_id": "tbl_001", "matrix": [["A", "B"]], "page_index": 0, "bbox_pt": [0, 0, 1, 1]}],
                "figures": [
                    {
                        "figure_id": "fig_001",
                        "page_index": 0,
                        "bbox_pt": [0, 0, 1, 1],
                        "markdown_ref": "![Figure](figures/fig_001.png)",
                        "png_path": "figures/fig_001.png",
                    }
                ],
                "metadata": {},
            },
        }
    }


def prediction_from_truth(truth_dir: Path, prediction_dir: Path) -> PredictionDocument:
    truth = _load_truth(truth_dir)
    markdown = (truth_dir / "document.md").read_text(encoding="utf-8")
    prediction = PredictionDocument(
        doc_id=truth.doc_id,
        markdown=markdown,
        blocks=[
            {
                "block_id": block.block_id,
                "type": block.type,
                "page_index": block.page_index,
                "bbox_pt": block.bbox_pt,
                "text": block.text,
                "markdown": block.markdown,
                "metadata": block.metadata,
            }
            for block in truth.blocks
        ],
        tables=[
            {
                "table_id": table.table_id,
                "matrix": table.matrix,
                "page_index": table.page_index,
                "bbox_pt": table.bbox_pt,
                "metadata": table.metadata,
            }
            for table in truth.tables
            if isinstance(table, TableBlock)
        ],
        figures=[
            {
                "figure_id": figure.figure_id,
                "page_index": figure.page_index,
                "bbox_pt": figure.bbox_pt,
                "markdown_ref": figure.markdown_ref,
                "png_path": figure.png_path,
                "metadata": figure.metadata,
            }
            for figure in truth.figures
            if isinstance(figure, FigureBlock)
        ],
        metadata={"parser": "dummy_truth_copy"},
    )
    prediction_dir.mkdir(parents=True, exist_ok=True)
    (prediction_dir / "document.md").write_text(markdown, encoding="utf-8")
    (prediction_dir / "prediction.json").write_text(prediction.model_dump_json(indent=2), encoding="utf-8")
    return prediction
