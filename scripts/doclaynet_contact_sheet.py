"""Contact sheets of pages with their boxes drawn, for looking at what a corpus actually contains.

    python scripts/doclaynet_contact_sheet.py real --survey output/doclaynet/survey --out output/doclaynet/sheets [--per-category 6]
    python scripts/doclaynet_contact_sheet.py synthetic ROOT --out output/doclaynet/sheets [--per-variant 6]

`real` picks seeded random pages of every DocLayNet document category, reading only the row groups it needs over HTTP range requests.
`synthetic` needs `export-coco ROOT` to have been run. One PNG per category (or variant); box colour is the class, drawn with its name.
"""

from __future__ import annotations

import argparse
import collections
import glob
import gzip
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

CATEGORIES = ["caption", "footnote", "formula", "list-item", "page-footer", "page-header", "picture", "section-header", "table", "text", "title"]
COLOURS = {"caption": "#e6194b", "footnote": "#f58231", "formula": "#911eb4", "list-item": "#3cb44b", "page-footer": "#808080", "page-header": "#a9a9a9",
           "picture": "#4363d8", "section-header": "#f032e6", "table": "#008080", "text": "#bfa100", "title": "#000075"}
CELL_H = 520
REPO = "datasets/docling-project/DocLayNet-v1.2/data"
SHARDS = {"train": 72, "validation": 7, "test": 6}


def draw(image: Image.Image, boxes: list[tuple[str, float, float, float, float]]) -> Image.Image:
    """Boxes are (class, x, y, w, h) as page fractions."""
    image = image.convert("RGB")
    scale = CELL_H / image.height
    image = image.resize((max(1, round(image.width * scale)), CELL_H))
    pen = ImageDraw.Draw(image)
    for name, x, y, w, h in boxes:
        x0, y0, x1, y1 = x * image.width, y * image.height, (x + w) * image.width, (y + h) * image.height
        pen.rectangle([x0, y0, x1, y1], outline=COLOURS[name], width=2)
        pen.text((x0 + 2, y0 + 1), name, fill=COLOURS[name])
    return image


def sheet(cells: list[Image.Image], columns: int = 3) -> Image.Image:
    rows = [cells[i : i + columns] for i in range(0, len(cells), columns)]
    width = max(sum(c.width for c in row) for row in rows)
    out = Image.new("RGB", (width, CELL_H * len(rows)), "white")
    for r, row in enumerate(rows):
        x = 0
        for cell in row:
            out.paste(cell, (x, r * CELL_H))
            x += cell.width
    return out


def real(survey: Path, out: Path, per_category: int, seed: int) -> None:
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    rng, fs = random.Random(seed), HfFileSystem()
    shard_of: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    for path in sorted(glob.glob(str(survey / "*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            first = json.loads(fh.readline())
        shard_of[first["category"]].append((first["split"], first["shard"]))
    for category, shards in sorted(shard_of.items()):
        cells = []
        for split, i in rng.sample(shards, min(len(shards), per_category + 6)):
            if len(cells) == per_category:
                break
            with fs.open(f"{REPO}/{split}-{i:05d}-of-{SHARDS[split]:05d}.parquet", "rb") as fh:
                parquet = pq.ParquetFile(fh)
                group = parquet.read_row_group(rng.randrange(parquet.metadata.num_row_groups), columns=["image", "bboxes", "category_id", "metadata"])
            own = [n for n, m in enumerate(group.column("metadata").to_pylist()) if m["doc_category"] == category]  # a shard can straddle two categories
            if not own:
                continue
            row = group.slice(rng.choice(own), 1).to_pylist()[0]
            meta = row["metadata"]
            w, h = float(meta["coco_width"]), float(meta["coco_height"])
            image = Image.open(io.BytesIO(row["image"]["bytes"]))
            image = image.resize((round(image.width * meta["original_width"] / meta["original_height"]), image.height))  # undo the squash to 1025 x 1025
            cells.append(draw(image, [(CATEGORIES[c - 1], b[0] / w, b[1] / h, b[2] / w, b[3] / h) for c, b in zip(row["category_id"], row["bboxes"])]))
        sheet(cells).save(out / f"real_{category}.png")
        print(category, len(cells), flush=True)


def synthetic(root: Path, out: Path, per_variant: int, seed: int) -> None:
    coco = json.loads((root / "coco_train.json").read_text())
    names = {c["id"]: c["name"] for c in coco["categories"]}
    boxes: dict[int, list] = collections.defaultdict(list)
    for a in coco["annotations"]:
        boxes[a["image_id"]].append(a)
    by_variant: dict[str, list[dict]] = collections.defaultdict(list)
    for im in coco["images"]:
        by_variant[im["doc_id"].rsplit("_", 2)[-2]].append(im)
    rng = random.Random(seed)
    for variant, images in sorted(by_variant.items()):
        cells = []
        for im in rng.sample(images, min(per_variant, len(images))):
            image = Image.open(root / im["file_name"])
            w, h = im["width"], im["height"]
            cells.append(draw(image, [(names[a["category_id"]], a["bbox"][0] / w, a["bbox"][1] / h, a["bbox"][2] / w, a["bbox"][3] / h) for a in boxes[im["id"]]]))
        sheet(cells).save(out / f"synthetic_{variant}.png")
        print(variant, len(cells), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("real")
    r.add_argument("--survey", type=Path, required=True)
    r.add_argument("--per-category", type=int, default=6)
    s = sub.add_parser("synthetic")
    s.add_argument("root", type=Path)
    s.add_argument("--per-variant", type=int, default=6)
    for p in (r, s):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    real(args.survey, args.out, args.per_category, args.seed) if args.command == "real" else synthetic(args.root, args.out, args.per_variant, args.seed)


if __name__ == "__main__":
    main()
