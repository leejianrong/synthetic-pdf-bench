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
        also_eval=[(root, coco)],
    )

    assert (out / "checkpoint.pt").exists()
    saved = json.loads((out / "report.json").read_text())
    assert saved == report
    assert {"map50_95", "map50", "per_class", "hardware", "steps", "n_val_images"} <= set(report)
    assert len(report["per_class"]) == 11
    assert report["steps"] == 2 and report["hardware"]["device"] == "cpu"
    assert 0.0 <= report["map50_95"] <= 1.0
    assert set(report["also"]) == {"coco"} and len(report["also"]["coco"]["per_class"]) == 11
    assert report["train_secs"] > 0 and report["eval_secs"] > 0
