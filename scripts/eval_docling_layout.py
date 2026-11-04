"""Score Docling's layout model (docling-layout-heron, RT-DETRv2, Apache-2.0) on a COCO page set, as a baseline.

Uses the same pages, boxes and COCO scorer as train_layout.py, so numbers are comparable. Needs torch, transformers,
pycocotools and rtod (for the shared scorer); see train_layout.py for the pinned install.

    python scripts/eval_docling_layout.py --root real --json real/coco_test.json --out run_docling

Heron predicts 17 classes. Labels 0-10 are DocLayNet's own 11 classes in id order. The extra ones are mapped as
below; a prediction of a class with no DocLayNet equivalent is dropped, and the count at score >= 0.6 (the model
card's threshold) is reported so the loss is visible. Docling was trained on DocLayNet train, so DocLayNet test is
its home set: read the result as an upper reference, not a fair fight.
"""

from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path

MODEL = "docling-project/docling-layout-heron"
SCORE_FLOOR = 0.01  # low, as in mAP evaluation; the model card's 0.6 is a deployment threshold
REPORT_SCORE = 0.6
# Heron label ids from the model card (the config's own names are lowercase with underscores, so match on ids).
EXTRA_LABELS = {11: 9, 12: 10}  # Document Index -> table, Code -> text (DocLayNet ids)
DROPPED = ("Checkbox-Selected", "Checkbox-Unselected", "Form", "Key-Value Region")  # ids 13-16


def to_doclaynet(label: int) -> int | None:
    """DocLayNet category id (1-11) for a heron label, or None if DocLayNet has no such class."""
    if label <= 10:
        return label + 1
    return EXTRA_LABELS.get(label)


def to_results(*, image_id: int, scores, labels, boxes, names: dict[int, str], keep_score: float) -> tuple[list[dict], dict[str, int]]:
    """COCO detection dicts (xywh, page pixels) for one page, and counts of dropped classes at or above `keep_score`."""
    results: list[dict] = []
    dropped: collections.Counter = collections.Counter()
    for score, label, (x0, y0, x1, y1) in zip(scores, labels, boxes, strict=True):
        category = to_doclaynet(int(label))
        if category is None:
            if score >= keep_score:
                dropped[names[int(label)]] += 1
            continue
        results.append({"image_id": image_id, "category_id": category, "bbox": [float(x0), float(y0), float(x1 - x0), float(y1 - y0)], "score": float(score)})
    return results, dict(dropped)


def _revision() -> str | None:
    try:
        from huggingface_hub import HfApi

        return HfApi().model_info(MODEL).sha
    except (ImportError, OSError):  # offline: the report just lacks the revision
        return None


def run(*, root: Path, coco_json: Path, out: Path, max_images: int | None = None) -> dict:
    import torch
    from PIL import Image
    from train_layout import LayoutPages, hardware, score_coco
    from transformers import RTDetrImageProcessor, RTDetrV2ForObjectDetection

    out.mkdir(parents=True, exist_ok=True)
    hw = hardware()
    print(f"STAGE model on {hw['device']} ({hw['name']})", flush=True)
    processor = RTDetrImageProcessor.from_pretrained(MODEL)
    model = RTDetrV2ForObjectDetection.from_pretrained(MODEL).to(hw["device"]).eval()
    names = {int(k): v for k, v in model.config.id2label.items()}
    data = LayoutPages(root, coco_json, 640, max_images)  # size is unused here; we only need the pages and boxes

    print("STAGE detect", flush=True)
    results: list[dict] = []
    dropped: collections.Counter = collections.Counter()
    t0 = time.monotonic()
    for n, info in enumerate(data.images, start=1):
        image = Image.open(root / info["file_name"]).convert("RGB")
        inputs = processor(images=[image], return_tensors="pt").to(hw["device"])
        with torch.no_grad():
            outputs = model(**inputs)
        det = processor.post_process_object_detection(outputs, target_sizes=torch.tensor([image.size[::-1]]), threshold=SCORE_FLOOR)[0]
        got, drop = to_results(image_id=info["id"], scores=det["scores"].tolist(), labels=det["labels"].tolist(), boxes=det["boxes"].tolist(),
                               names=names, keep_score=REPORT_SCORE)
        results += got
        dropped.update(drop)
        if n % 25 == 0 or n == len(data.images):
            print(f"DETECT page={n}/{len(data.images)} secs={time.monotonic() - t0:.0f}", flush=True)
    detect_secs = time.monotonic() - t0

    print("STAGE score", flush=True)
    report = {**score_coco(data, results), "model": MODEL, "revision": _revision(), "hardware": hw,
              "score_floor": SCORE_FLOOR, "n_images": len(data), "detect_secs": detect_secs,
              "extra_label_mapping": {"Document Index": "table", "Code": "text"},
              "dropped_at_0.6": dict(dropped), "dropped_classes": list(DROPPED)}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("REPORT " + json.dumps({k: report[k] for k in ("map50_95", "map50")}), flush=True)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, required=True, help="Directory the COCO file_name paths are relative to.")
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-images", type=int)
    a = p.parse_args()
    run(root=a.root, coco_json=a.json, out=a.out, max_images=a.max_images)


if __name__ == "__main__":
    main()
