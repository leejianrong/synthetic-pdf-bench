import json
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.export.coco import CATEGORIES, export_coco
from synthetic_pdf_bench.export.datasets import write_hf_imagefolder, write_yolo

RECIPES = [Path("data/recipes/canonical/sea_historical_report_v1.json"), Path("data/recipes/canonical/visual_benchmark_v1.json")]


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "ds"
    generate_dataset(root, count=4, recipe_paths=RECIPES, splits={"train": 0.5, "val": 0.5})
    return root


def test_yolo_labels_match_coco_and_follow_splits(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    out = write_yolo(root, tmp_path / "yolo")
    coco = export_coco(root)

    assert all(c in (out / "data.yaml").read_text() for c in CATEGORIES)
    labels = sorted(out.glob("labels/*/*.txt"))
    images = sorted(out.glob("images/*/*.png"))
    assert len(labels) == len(images) == len(coco["images"])
    assert {p.parent.name for p in labels} == {"train", "val"}
    n_boxes = sum(len(p.read_text().splitlines()) for p in labels)
    assert n_boxes == len(coco["annotations"])
    cls, cx, cy, w, h = map(float, labels[0].read_text().splitlines()[0].split())
    assert 0 <= cls < len(CATEGORIES) and all(0 <= v <= 1 for v in (cx, cy, w, h))


def test_hf_imagefolder_has_objects_and_card(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    out = write_hf_imagefolder(root, tmp_path / "hf")
    rows = [json.loads(line) for line in (out / "train/metadata.jsonl").read_text().splitlines()]

    assert (out / "train" / rows[0]["file_name"]).exists()
    objects = rows[0]["objects"]
    assert len(objects["bbox"]) == len(objects["category"]) == len(objects["reading_order"]) > 0
    assert "val" in {p.name for p in out.iterdir() if p.is_dir()}
    assert "bbox" in (out / "README.md").read_text()
