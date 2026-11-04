import json
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.evaluation.evaluator import (
    evaluate_prediction,
    prediction_from_truth,
)


def test_dummy_prediction_scores_perfectly(tmp_path: Path) -> None:
    output = tmp_path / "doc"
    prediction = tmp_path / "prediction"
    generate(output, seed=123)

    prediction_from_truth(output / "truth", prediction)
    report = evaluate_prediction(output / "truth", prediction)

    assert report["markdown"]["normalized_exact_match"] is True
    assert report["markdown"]["f1"] == 1.0
    assert report["markdown"]["edit_similarity"] == 1.0
    assert report["blocks"]["reading_order"] == 1.0
    assert report["blocks"]["mean_bbox_iou"] == 1.0
    assert report["tables"]["exact_match_rate"] == 1.0
    assert report["tables"]["mean_teds"] == 1.0
    assert report["figures"]["count_match"] is True
    assert report["figures"]["mean_bbox_iou"] == 1.0
    assert report["figures"]["markdown_ref_match_rate"] == 1.0


def test_markdown_only_prediction_gets_text_score_without_structure(tmp_path: Path) -> None:
    output = tmp_path / "doc"
    prediction = tmp_path / "prediction"
    generate(output, seed=123)
    prediction.mkdir()
    (prediction / "document.md").write_text("Singapore Malaysia Indonesia", encoding="utf-8")

    report = evaluate_prediction(output / "truth", prediction)

    assert report["markdown"]["f1"] > 0
    assert report["blocks"]["matched_by_id"] == 0
    assert report["tables"]["exact_match_rate"] == 0
    assert report["tables"]["mean_teds"] == 0
    assert report["figures"]["count_match"] is False


def test_shuffled_blocks_lower_the_reading_order_score(tmp_path: Path) -> None:
    output = tmp_path / "doc"
    prediction = tmp_path / "prediction"
    generate(output, seed=123)
    prediction_from_truth(output / "truth", prediction)
    path = prediction / "prediction.json"
    data = json.loads(path.read_text())
    data["blocks"] = data["blocks"][::2] + data["blocks"][1::2]
    path.write_text(json.dumps(data))

    report = evaluate_prediction(output / "truth", prediction)

    assert 0.5 < report["blocks"]["reading_order"] < 1.0
    assert report["overall"]["reading_order"] == report["blocks"]["reading_order"]
