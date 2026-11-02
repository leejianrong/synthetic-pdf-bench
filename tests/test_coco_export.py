import json
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.export.coco import (
    BLOCK_TYPE_TO_CATEGORY,
    export_coco,
    write_coco,
)
from synthetic_pdf_bench.schema.truth import DocumentTruth


def test_coco_export_matches_truth(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=123)
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())

    coco = export_coco(tmp_path / "doc")

    assert len(coco["images"]) == len(truth.pages)
    assert len(coco["annotations"]) == sum(len(p.blocks) for p in truth.pages)
    assert all((tmp_path / "doc" / i["file_name"]).exists() for i in coco["images"])
    first = coco["annotations"][0]
    assert first["bbox"][2] > 0 and first["bbox"][3] > 0
    page_orders = [a["reading_order"] for a in coco["annotations"] if a["image_id"] == 1]
    assert page_orders == sorted(page_orders) == list(range(len(page_orders)))


def test_every_generated_block_type_has_a_category(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=123)
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())
    assert {b.type for b in truth.blocks} <= set(BLOCK_TYPE_TO_CATEGORY)


def test_dataset_root_export_writes_relative_paths(tmp_path: Path) -> None:
    generate(tmp_path / "a", seed=1)
    generate(tmp_path / "b", seed=2)

    out = write_coco(tmp_path)

    coco = json.loads(out.read_text())
    assert {i["file_name"].split("/")[0] for i in coco["images"]} == {"a", "b"}
