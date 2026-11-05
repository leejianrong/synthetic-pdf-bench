from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.evaluation.evaluator import (
    evaluate_prediction,
    prediction_from_truth,
)
from synthetic_pdf_bench.evaluation.matching import assign_truth_ids
from synthetic_pdf_bench.evaluation.prediction import PredictionDocument
from synthetic_pdf_bench.schema.truth import DocumentTruth


def _shift(box: list[float] | None) -> list[float] | None:
    return None if box is None else [box[0] + 1.5, box[1] - 1.0, box[2] + 1.5, box[3] - 1.0]


def test_geometry_matching_gives_a_parser_the_truth_ids_it_cannot_know(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=123)
    truth_dir = tmp_path / "doc" / "truth"
    prediction_dir = tmp_path / "pred"
    prediction = prediction_from_truth(truth_dir, prediction_dir)
    truth = DocumentTruth.model_validate_json((truth_dir / "document.json").read_text())

    renamed = PredictionDocument(markdown=prediction.markdown)
    for n, block in enumerate(prediction.blocks):
        renamed.blocks.append(block.model_copy(update={"block_id": f"parser-{n}", "bbox_pt": _shift(block.bbox_pt)}))
    for n, table in enumerate(prediction.tables):
        renamed.tables.append(table.model_copy(update={"table_id": f"t{n}", "bbox_pt": _shift(table.bbox_pt)}))
    for n, figure in enumerate(prediction.figures):
        renamed.figures.append(figure.model_copy(update={"figure_id": f"f{n}", "bbox_pt": _shift(figure.bbox_pt)}))
    assert renamed.tables and renamed.figures

    matched = assign_truth_ids(renamed, truth)
    (prediction_dir / "prediction.json").write_text(matched.model_dump_json())
    report = evaluate_prediction(truth_dir, prediction_dir)

    assert report["blocks"]["matched_by_id"] == len(truth.blocks)
    assert 0.8 < report["blocks"]["mean_bbox_iou"] < 1.0
    assert report["blocks"]["reading_order"] == 1.0
    assert report["tables"]["mean_teds"] == 1.0
    assert 0.8 < report["figures"]["mean_bbox_iou"] < 1.0


def test_a_box_far_from_every_truth_box_keeps_its_own_id(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=123)
    truth = DocumentTruth.model_validate_json((tmp_path / "doc" / "truth" / "document.json").read_text())
    stray = PredictionDocument.model_validate(
        {"blocks": [{"block_id": "stray", "type": "text", "page_index": 0, "bbox_pt": [0.0, 0.0, 5.0, 5.0]}]}
    )

    assert [b.block_id for b in assign_truth_ids(stray, truth).blocks] == ["stray"]
