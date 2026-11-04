"""Fine-tune YOLOX-Tiny (Apache-2.0) for page layout detection on a COCO-format export, then report mAP.

Needs torch, pycocotools and rtod's vendored YOLOX; pin rtod by commit, e.g.

    uv run --with "rtod[torch,coco] @ git+https://github.com/leejianrong/real-time-object-detection@3751bc7146a7491152facc6d6fb31b0544f37a69" \\
        python scripts/train_layout.py --root output/corpus --train-json output/corpus/coco_train.json \\
        --val-json output/corpus/coco_val.json --out output/run1 --steps 2000

The log has grep-able markers (STAGE, TRAIN, REPORT) for a pod driver. No horizontal flip: mirrored text is not a page.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from rtod.detect import letterbox, postprocess
from rtod.models import build_yolox_tiny, fetch_official_weights
from torch.utils.data import ConcatDataset, DataLoader, Dataset, WeightedRandomSampler

MAX_LABELS = 200  # dense pages: far above the 120 used for COCO photos


def stage(name: str) -> None:
    print(f"STAGE {name}", flush=True)


def hardware() -> dict:
    cuda = torch.cuda.is_available()
    lines = Path("/proc/cpuinfo").read_text().splitlines() if Path("/proc/cpuinfo").exists() else []
    cpu = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("model name")), platform.processor())
    return {
        "device": "cuda" if cuda else "cpu",
        "name": torch.cuda.get_device_name(0) if cuda else cpu,
        "torch": torch.__version__,
        "cpu_count": torch.get_num_threads(),
    }


def augment_page(img: np.ndarray, boxes: list, rng: random.Random) -> tuple[np.ndarray, list]:
    """Mild photometric jitter and zoom-out (shrink the page onto a larger white canvas). No flips: mirrored text is not a page.

    ``boxes`` are [cls, x, y, w, h] in image pixels.
    """
    if rng.random() < 0.5:
        img = np.clip(img.astype(np.float32) * rng.uniform(0.8, 1.2) + rng.uniform(-20, 20), 0, 255).astype(np.uint8)
    if rng.random() < 0.3:
        scale = rng.uniform(0.7, 1.0)
        h, w = img.shape[:2]
        big_h, big_w = int(h / scale), int(w / scale)
        ox, oy = rng.randint(0, big_w - w), rng.randint(0, big_h - h)
        canvas = np.full((big_h, big_w, 3), 255, dtype=np.uint8)
        canvas[oy : oy + h, ox : ox + w] = img
        img, boxes = canvas, [[c, x + ox, y + oy, bw, bh] for c, x, y, bw, bh in boxes]
    return img, boxes


class LayoutPages(Dataset):
    """Pages and boxes from a COCO json written by `export-coco`; targets are [cls, cx, cy, w, h] in input pixels."""

    def __init__(self, root: Path, coco_json: Path, size: int, max_images: int | None = None, augment: bool = False) -> None:
        data = json.loads(coco_json.read_text(encoding="utf-8"))
        self.root, self.size, self.augment = root, size, augment
        self.images = data["images"][:max_images]
        self.names = {c["id"]: c["name"] for c in data["categories"]}
        self.categories = sorted(self.names)
        self.boxes: dict[int, list] = {i["id"]: [] for i in self.images}
        for a in data["annotations"]:
            if a["image_id"] in self.boxes:
                self.boxes[a["image_id"]].append([self.categories.index(a["category_id"]), *a["bbox"]])

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, i: int):
        info = self.images[i]
        img = cv2.imread(str(self.root / info["file_name"]))
        raw = self.boxes[info["id"]]
        if self.augment:
            img, raw = augment_page(img, raw, random)  # the module `random` is reseeded per DataLoader worker
        blob, ratio = letterbox(img, self.size)
        boxes = np.array(raw, dtype=np.float32).reshape(-1, 5)[:MAX_LABELS]
        t = np.zeros((MAX_LABELS, 5), dtype=np.float32)
        t[: len(boxes), 0] = boxes[:, 0]
        t[: len(boxes), 1:3] = (boxes[:, 1:3] + boxes[:, 3:5] / 2) * ratio
        t[: len(boxes), 3:5] = boxes[:, 3:5] * ratio
        return blob[0], t


def build_model(num_classes: int, weights: Path | None):
    """YOLOX-Tiny with a fresh class head; backbone, neck and box/objectness heads come from `weights` (COCO) if given."""
    model = build_yolox_tiny(num_classes)
    if weights is not None:
        state = torch.load(weights, map_location="cpu")["model"]
        own = model.state_dict()
        model.load_state_dict({k: v for k, v in state.items() if k in own and own[k].shape == v.shape}, strict=False)
    return model


def train(model, data: Dataset, *, steps: int, batch: int, lr: float, device: str, workers: int, seed: int, sampler=None) -> None:
    loader = DataLoader(
        data, batch_size=batch, shuffle=sampler is None, sampler=sampler, num_workers=workers, drop_last=len(data) >= batch,
        generator=torch.Generator().manual_seed(seed),
    )
    model.head.decode_in_inference = False
    model.to(device).train()
    decay = [p for p in model.parameters() if p.ndim > 1]
    rest = [p for p in model.parameters() if p.ndim <= 1]
    opt = torch.optim.SGD([{"params": decay, "weight_decay": 5e-4}, {"params": rest, "weight_decay": 0.0}], lr=lr, momentum=0.9, nesterov=True)
    warmup, step, t0 = min(100, steps // 10), 0, time.monotonic()
    while step < steps:
        for x, y in loader:
            ramp = min(1.0, (step + 1) / warmup) if warmup else 1.0
            for g in opt.param_groups:
                g["lr"] = ramp * lr * 0.5 * (1 + math.cos(math.pi * step / steps))
            out = model(x.to(device), y.to(device))
            opt.zero_grad()
            out["total_loss"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 100.0)
            opt.step()
            step += 1
            loss = float(out["total_loss"])
            if not math.isfinite(loss):  # fail in seconds, not after the run has burned money
                raise FloatingPointError(f"non-finite loss {loss} at step {step}")
            if step in (1, steps) or step % 10 == 0:
                rate = step / (time.monotonic() - t0)
                mem = torch.cuda.max_memory_allocated() // 2**20 if device == "cuda" else 0
                print(f"TRAIN step={step}/{steps} loss={loss:.3f} iou={float(out['iou_loss']):.3f} conf={float(out['conf_loss']):.3f} "
                      f"cls={float(out['cls_loss']):.3f} lr={opt.param_groups[0]['lr']:.2e} it_s={rate:.2f} eta_s={(steps - step) / rate:.0f} "
                      f"gpu_mem_mb={mem}", flush=True)
            if step >= steps:
                break


def score_coco(data: LayoutPages, results: list[dict]) -> dict:
    """COCO mAP of `results` (image_id, category_id, xywh bbox, score) against the pages' ground truth."""
    gt = {"images": [{"id": i["id"], "width": i["width"], "height": i["height"]} for i in data.images],
          "annotations": [], "categories": [{"id": c, "name": str(c)} for c in data.categories]}
    for info in data.images:
        for cls, x, y, w, h in data.boxes[info["id"]]:
            gt["annotations"].append({"id": len(gt["annotations"]) + 1, "image_id": info["id"], "category_id": data.categories[int(cls)],
                                      "bbox": [x, y, w, h], "area": w * h, "iscrowd": 0})
    coco = COCO()
    coco.dataset = gt
    coco.createIndex()
    if not results:
        return {"map50_95": 0.0, "map50": 0.0, "per_class": {data.names[c]: 0.0 for c in data.categories}}
    ev = COCOeval(coco, coco.loadRes(results), "bbox")
    ev.evaluate()
    ev.accumulate()
    ev.summarize()
    precision = ev.eval["precision"]  # (T, R, K, A, M)
    per_class = {}
    for k, c in enumerate(data.categories):
        p = precision[:, :, k, 0, 2]
        per_class[data.names[c]] = float(p[p > -1].mean()) if (p > -1).any() else 0.0
    return {"map50_95": float(ev.stats[0]), "map50": float(ev.stats[1]), "per_class": per_class}


@torch.no_grad()
def evaluate(model, data: LayoutPages, device: str, size: int) -> dict:
    """COCO mAP over the pages. Boxes are in the exported images' pixels, same as the ground truth."""
    model.head.decode_in_inference = True
    model.to(device).eval()
    results = []
    for info in data.images:
        img = cv2.imread(str(data.root / info["file_name"]))
        blob, ratio = letterbox(img, size)
        raw = model(torch.from_numpy(blob).to(device))[0].cpu().numpy()
        det = postprocess(raw, ratio, img.shape, conf=0.001, iou=0.65)
        for (x1, y1, x2, y2), s, c in zip(det.boxes, det.scores, det.class_ids, strict=True):
            results.append({"image_id": info["id"], "category_id": data.categories[int(c)], "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)], "score": float(s)})
    return score_coco(data, results)


def run(*, root: Path, train_json: Path, val_json: Path, out: Path, steps: int, batch: int, size: int, weights: Path | None,
        workers: int, seed: int, lr: float = 0.005, max_train_images: int | None = None, max_val_images: int | None = None,
        also_eval: list[tuple[Path, Path]] = (), also_train: list[tuple[Path, Path, float]] = (), augment: bool = False) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    out.mkdir(parents=True, exist_ok=True)
    hw = hardware()
    stage(f"data on {hw['device']} ({hw['name']})")
    sets = [LayoutPages(root, train_json, size, max_train_images, augment)]
    sets += [LayoutPages(r, j, size, augment=augment) for r, j, _ in also_train]
    shares = [1.0 - sum(sh for *_, sh in also_train), *(sh for *_, sh in also_train)]
    if shares[0] <= 0 or any(sh <= 0 for sh in shares):
        raise ValueError(f"train shares must be positive and leave the first set a share, got {shares}")
    if any(d.names != sets[0].names for d in sets):
        raise ValueError("train sets must use the same categories")
    train_data = sets[0]
    mix = [{"pages": len(d), "share": sh} for d, sh in zip(sets, shares, strict=True)]
    val_data = LayoutPages(root, val_json, size, max_val_images)
    stage("model")
    model = build_model(len(train_data.categories), weights)
    stage("train")
    t0 = time.monotonic()
    sampler = None
    if len(sets) > 1:  # each draw comes from set i with probability share_i
        weights = [sh / len(d) for d, sh in zip(sets, shares, strict=True) for _ in range(len(d))]
        sampler = WeightedRandomSampler(weights, num_samples=steps * batch, replacement=True, generator=torch.Generator().manual_seed(seed))
    train(model, ConcatDataset(sets) if sampler else train_data, steps=steps, batch=batch, lr=lr, device=hw["device"], workers=workers, seed=seed, sampler=sampler)
    train_secs = time.monotonic() - t0
    torch.save(model.state_dict(), out / "checkpoint.pt")
    stage("evaluate")
    t0 = time.monotonic()
    report = {**evaluate(model, val_data, hw["device"], size), "hardware": hw, "steps": steps, "batch": batch, "size": size, "lr": lr,
              "n_train_images": sum(m["pages"] for m in mix), "mix": mix, "augment": augment, "n_val_images": len(val_data), "weights": str(weights) if weights else None}
    # More datasets scored with the same model, e.g. real pages: {json stem: metrics}. Pass the pages' own root.
    report["also"] = {}
    for r, j in also_eval:  # not capped by max_val_images: these are explicit samples
        pages = LayoutPages(r, j, size)
        report["also"][j.stem] = {**evaluate(model, pages, hw["device"], size), "n_images": len(pages)}
    report |= {"train_secs": train_secs, "eval_secs": time.monotonic() - t0}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("REPORT " + json.dumps({k: report[k] for k in ("map50_95", "map50")}), flush=True)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, required=True, help="Directory the COCO file_name paths are relative to.")
    p.add_argument("--train-json", type=Path, required=True)
    p.add_argument("--val-json", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--steps", type=int, required=True)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--size", type=int, default=640)
    p.add_argument("--lr", type=float, default=0.005)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--weights", default="official", help="'official' downloads the COCO checkpoint, 'none' trains from random, or a path.")
    p.add_argument("--max-train-images", type=int)
    p.add_argument("--max-val-images", type=int)
    p.add_argument("--also-train", action="append", default=[], metavar="ROOT:JSON:SHARE", help="Mix in this train set; SHARE (0-1) of the draws. The first set takes the rest.")
    p.add_argument("--augment", action="store_true", help="Mild photometric jitter and zoom-out on training pages.")
    p.add_argument("--also-eval", action="append", default=[], metavar="ROOT:JSON", help="Also score this dataset (repeatable).")
    a = p.parse_args()
    weights = None if a.weights == "none" else fetch_official_weights() if a.weights == "official" else Path(a.weights)
    run(root=a.root, train_json=a.train_json, val_json=a.val_json, out=a.out, steps=a.steps, batch=a.batch, size=a.size, weights=weights,
        workers=a.workers, seed=a.seed, lr=a.lr, max_train_images=a.max_train_images, max_val_images=a.max_val_images,
        also_eval=[(Path(r), Path(j)) for r, j in (x.split(":", 1) for x in a.also_eval)],
        also_train=[(Path(r), Path(j), float(sh)) for r, j, sh in (x.rsplit(":", 2) for x in a.also_train)], augment=a.augment)


if __name__ == "__main__":
    sys.exit(main())
