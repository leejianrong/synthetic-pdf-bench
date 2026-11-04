"""Sample real pages from DocLayNet-v1.2 (CDLA-Permissive-1.0) into the COCO layout `train_layout.py` reads.

The parquet shards are sorted by document category, so one shard is one category. To keep a sample
representative this downloads evenly spaced shards, takes an equal seeded quota of pages from each,
deletes each shard after use, and logs the category mix.

    python scripts/prepare_doclaynet.py --out data_real --split test --use 6 --n 500 --seed 0

DocLayNet class ids 1..11 are already in the order of our `export-coco` categories.
Needs pyarrow and pillow. Pods have no GPU need: this is CPU and network only.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import time
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

URL = "https://huggingface.co/datasets/docling-project/DocLayNet-v1.2/resolve/main/data/{split}-{i:05d}-of-{n:05d}.parquet"
SHARDS = {"train": 72, "validation": 7, "test": 6}
CATEGORIES = ["caption", "footnote", "formula", "list-item", "page-footer", "page-header", "picture", "section-header", "table", "text", "title"]
COLUMNS = ["image", "bboxes", "category_id", "metadata"]  # skips the PDF bytes and cell text


def stage(name: str) -> None:
    print(f"STAGE {name}", flush=True)


def spread(total: int, use: int) -> list[int]:
    """`use` evenly spaced shard indices out of `total`."""
    if not 1 <= use <= total:
        raise ValueError(f"cannot use {use} of {total} shards")
    return [i * total // use for i in range(use)]


def download(split: str, index: int, cache: Path, retries: int = 3) -> Path:
    path = cache / f"{split}-{index:05d}.parquet"
    if path.exists():
        return path
    cache.mkdir(parents=True, exist_ok=True)
    url = URL.format(split=split, i=index, n=SHARDS[split])
    for attempt in range(1, retries + 1):
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, open(path.with_suffix(".part"), "wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
            path.with_suffix(".part").rename(path)
            print(f"DOWNLOAD {path.name} bytes={path.stat().st_size} secs={time.monotonic() - t0:.0f}", flush=True)
            return path
        except OSError as err:
            print(f"WARN download {path.name} attempt {attempt}/{retries}: {err}", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"could not download {url}")


def convert_shard(path: Path, out: Path, *, split: str, shard_index: int, quota: int, seed: int, first_id: int) -> tuple[list[dict], list[dict]]:
    """Take `quota` seeded rows from one shard; write their PNGs; return COCO image and annotation dicts."""
    file = pq.ParquetFile(path)
    rows = file.metadata.num_rows
    picks = sorted(random.Random(f"{seed}-{split}-{shard_index}").sample(range(rows), min(quota, rows)))
    images: list[dict] = []
    annotations: list[dict] = []
    (out / "images" / split).mkdir(parents=True, exist_ok=True)
    start = 0
    for group in range(file.num_row_groups):
        size = file.metadata.row_group(group).num_rows
        wanted = [p - start for p in picks if start <= p < start + size]
        start += size
        if not wanted:
            continue
        for row in file.read_row_group(group, columns=COLUMNS).take(wanted).to_pylist():
            meta = row["metadata"]
            name = f"images/{split}/{split}_{shard_index:02d}_{meta['page_hash'][:12]}.png"
            (out / name).write_bytes(row["image"]["bytes"])
            image_id, width, height = first_id + len(images), meta["coco_width"], meta["coco_height"]
            images.append({"id": image_id, "file_name": name, "width": width, "height": height, "doc_category": meta["doc_category"],
                           "original_filename": meta["original_filename"], "page_no": meta["page_no"], "page_hash": meta["page_hash"]})
            for (x, y, w, h), category in zip(row["bboxes"], row["category_id"], strict=True):
                x0, y0, x1, y1 = max(0.0, x), max(0.0, y), min(float(width), x + w), min(float(height), y + h)
                if x1 - x0 < 1 or y1 - y0 < 1:
                    continue
                annotations.append({"id": 0, "image_id": image_id, "category_id": category, "bbox": [x0, y0, x1 - x0, y1 - y0],
                                    "area": (x1 - x0) * (y1 - y0), "iscrowd": 0})
    return images, annotations


def write_coco(out: Path, split: str, images: list[dict], annotations: list[dict]) -> Path:
    for n, ann in enumerate(annotations, start=1):
        ann["id"] = n
    path = out / f"coco_{split}.json"
    path.write_text(json.dumps({"images": images, "annotations": annotations, "categories": [{"id": i, "name": c} for i, c in enumerate(CATEGORIES, start=1)]}))
    return path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--split", choices=SHARDS, required=True)
    p.add_argument("--use", type=int, required=True, help="How many evenly spaced shards to draw from.")
    p.add_argument("--n", type=int, required=True, help="Total pages to sample.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cache", type=Path, default=Path("shard_cache"))
    p.add_argument("--keep", action="store_true", help="Keep downloaded shards (default: delete each after use).")
    p.add_argument("--shards", help="Comma-separated shard indices, overriding --use (for a local rehearsal).")
    a = p.parse_args()
    shards = [int(s) for s in a.shards.split(",")] if a.shards else spread(SHARDS[a.split], a.use)
    quotas = [a.n // len(shards) + (i < a.n % len(shards)) for i in range(len(shards))]
    images: list[dict] = []
    annotations: list[dict] = []
    for index, quota in zip(shards, quotas, strict=True):
        stage(f"{a.split} shard {index} quota {quota}")
        path = download(a.split, index, a.cache)
        got_images, got_annotations = convert_shard(path, a.out, split=a.split, shard_index=index, quota=quota, seed=a.seed, first_id=len(images) + 1)
        images += got_images
        annotations += got_annotations
        if not a.keep:
            path.unlink()
    coco = write_coco(a.out, a.split, images, annotations)
    pages = [{k: i[k] for k in ("id", "original_filename", "page_no", "page_hash", "doc_category")} for i in images]
    (a.out / f"pages_{a.split}.json").write_text(json.dumps(pages, indent=1))
    print("PREP " + json.dumps({"split": a.split, "shards": shards, "images": len(images), "boxes": len(annotations),
                                "doc_category": collections.Counter(i["doc_category"] for i in images),
                                "class": {CATEGORIES[c - 1]: n for c, n in sorted(collections.Counter(x["category_id"] for x in annotations).items())}}), flush=True)
    print(f"REPORT wrote {coco}", flush=True)


if __name__ == "__main__":
    main()
