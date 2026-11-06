"""Rehearsal of the layout training script on CPU. Skipped unless the optional training stack is installed:

    uv run --with "rtod[torch,coco] @ git+https://github.com/leejianrong/real-time-object-detection@3751bc7146a7491152facc6d6fb31b0544f37a69" pytest tests/test_train_layout.py
"""

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("rtod.models")
pytest.importorskip("pycocotools")

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.export.coco import write_coco

SCRIPT = Path(__file__).parents[1] / "scripts" / "train_layout.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("train_layout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_two_step_cpu_run_trains_and_reports_map(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    generate_dataset(root, count=2, recipe_paths=[Path("data/recipes/canonical/sea_historical_report_v1.json")])
    coco = write_coco(root)
    out = tmp_path / "out"

    report = _load_script().run(
        root=root, train_json=coco, val_json=coco, out=out, steps=2, batch=2, size=320, weights=None, workers=0, seed=0,
        also_eval=[(root, coco)], max_val_images=1,
    )

    assert (out / "checkpoint.pt").exists()
    saved = json.loads((out / "report.json").read_text())
    assert saved == report
    assert {"map50_95", "map50", "per_class", "hardware", "steps", "n_val_images"} <= set(report)
    assert len(report["per_class"]) == 11
    assert report["steps"] == 2 and report["hardware"]["device"] == "cpu"
    assert 0.0 <= report["map50_95"] <= 1.0
    assert set(report["also"]) == {"coco"} and len(report["also"]["coco"]["per_class"]) == 11
    assert report["n_val_images"] == 1 and report["also"]["coco"]["n_images"] > 1  # the cap spares also-eval pages
    assert report["train_secs"] > 0 and report["eval_secs"] > 0


class _Always:
    """Stands in for `random`: every probability test fires, and ranges resolve to fixed values."""

    @staticmethod
    def random() -> float:
        return 0.0

    @staticmethod
    def uniform(lo: float, hi: float) -> float:
        return lo

    @staticmethod
    def randint(lo: int, hi: int) -> int:
        return hi


def test_augment_page_keeps_boxes_on_their_content() -> None:
    import numpy as np

    img = np.full((100, 200, 3), 255, dtype=np.uint8)
    img[20:40, 50:150] = 0  # the "text" the box covers
    out, boxes = _load_script().augment_page(img, [[3, 50, 20, 100, 20]], _Always)

    (cls, x, y, w, h), = boxes
    assert cls == 3 and (w, h) == (100, 20)
    assert out.shape[0] > 100 and out.shape[1] > 200  # zoomed out
    assert out[int(y) : int(y + h), int(x) : int(x + w)].mean() < 40  # still dark where the box says


def test_mixed_run_reports_the_mix_and_rejects_bad_shares(tmp_path: Path) -> None:
    root = tmp_path / "ds"
    generate_dataset(root, count=2, recipe_paths=[Path("data/recipes/canonical/sea_historical_report_v1.json")])
    coco = write_coco(root)
    kw = {"root": root, "train_json": coco, "val_json": coco, "out": tmp_path / "out", "steps": 2, "batch": 2, "size": 320, "weights": None, "workers": 0, "seed": 0}

    report = _load_script().run(**kw, also_train=[(root, coco, 0.25)], augment=True)

    assert [m["share"] for m in report["mix"]] == [0.75, 0.25] and report["augment"] is True
    assert report["n_train_images"] == 2 * len(json.loads(coco.read_text())["images"])
    with pytest.raises(ValueError, match="shares"):
        _load_script().run(**kw, also_train=[(root, coco, 1.0)])


def test_own_checkpoint_loads_as_starting_weights(tmp_path: Path) -> None:
    import torch

    module = _load_script()
    first = module.build_model(11, None)
    torch.save(first.state_dict(), tmp_path / "ckpt.pt")

    second = module.build_model(11, tmp_path / "ckpt.pt")

    key = next(k for k in first.state_dict() if k.endswith("cls_preds.0.weight"))
    assert torch.equal(first.state_dict()[key], second.state_dict()[key])  # the class head came along too


def test_scores_are_split_by_document_category(tmp_path: Path) -> None:
    script = _load_script()
    box = {"category_id": 1, "bbox": [10, 10, 50, 50]}
    coco = {"categories": [{"id": 1, "name": "text"}],
            "images": [{"id": 1, "file_name": "a.png", "width": 100, "height": 100, "doc_category": "manuals"},
                       {"id": 2, "file_name": "b.png", "width": 100, "height": 100, "doc_category": "patents"}],
            "annotations": [{"id": 1, "image_id": 1, **box}, {"id": 2, "image_id": 2, **box}]}
    path = tmp_path / "coco.json"
    path.write_text(json.dumps(coco))
    pages = script.LayoutPages(tmp_path, path, 640)
    results = [{"image_id": 1, **box, "score": 0.9}]  # found on the manuals page, missed on the patents page

    scores = script.score_by_category(pages, results)

    assert scores["manuals"] == {"map50_95": pytest.approx(1.0), "n_images": 1}
    assert scores["patents"] == {"map50_95": 0.0, "n_images": 1}
