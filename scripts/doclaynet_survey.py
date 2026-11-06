"""Per-page survey records for DocLayNet-v1.2 and for our synthetic pages, in one format so the two can be compared.

    python scripts/doclaynet_survey.py fetch --out output/doclaynet/survey [--splits train validation test] [--workers 4]
    python scripts/doclaynet_survey.py synthetic ROOT --out output/doclaynet/survey_synthetic.jsonl.gz
    python scripts/doclaynet_survey.py bank output/doclaynet/survey --out output/doclaynet/bank.jsonl.gz [--docs-per-category 100]

`fetch` reads only the small parquet columns (boxes, classes, metadata, text cells) over HTTP range requests, so no page image or
PDF is downloaded. Output is gzipped JSON lines, one page per line:

    {"split", "shard", "category", "collection", "doc", "page_no", "num_pages", "w_pt", "h_pt", "cells", "chars",
     "boxes": [[class, x, y, w, h, n_cells, n_chars, cell_h_pt, font]]}

Box coordinates are fractions of the page (DocLayNet squashes every page to 1025 x 1025 px, so pixels are not comparable across pages).
`cell_h_pt` is the median text-cell height in points, a proxy for type size (the font size field in DocLayNet is a scale factor, not points).
`font` is the most common font name among the box's cells, subset prefix removed. Each text cell is assigned to the smallest box that
contains its centre; cells inside no box are counted in the page's `cells` and `chars` totals only.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

CATEGORIES = ["caption", "footnote", "formula", "list-item", "page-footer", "page-header", "picture", "section-header", "table", "text", "title"]
REPO = "datasets/docling-project/DocLayNet-v1.2/data"
SHARDS = {"train": 72, "validation": 7, "test": 6}
COLUMNS = ["bboxes", "category_id", "metadata", "pdf_cells"]


def strip_font(name: str | None) -> str:
    name = (name or "").strip("/")
    return name.split("+", 1)[1] if len(name) > 7 and name[6] == "+" else name


def box_record(category: str, box: tuple[float, float, float, float], cells: list[tuple[float, str, str]], h_pt: float) -> list:
    """`cells` are (height as a page fraction, text, font) for the cells assigned to this box."""
    heights = [h for h, _, _ in cells]
    fonts = collections.Counter(font for _, _, font in cells)
    return [
        category,
        *(round(v, 5) for v in box),
        len(cells),
        sum(len(text) for _, text, _ in cells),
        round(statistics.median(heights) * h_pt, 2) if heights else None,
        fonts.most_common(1)[0][0] if fonts else None,
    ]


def real_page(row: dict, split: str, shard: int) -> dict:
    meta = row["metadata"]
    w_px, h_px = float(meta["coco_width"]), float(meta["coco_height"])
    boxes = [(b[0] / w_px, b[1] / h_px, b[2] / w_px, b[3] / h_px) for b in row["bboxes"]]  # x, y, w, h as page fractions
    owned: list[list] = [[] for _ in boxes]
    cells = [c for group in row["pdf_cells"] for c in (group if isinstance(group, list) else [group])] if row["pdf_cells"] else []
    chars = 0
    for cell in cells:
        text = cell.get("text") or ""
        chars += len(text)
        x, y, w, h = cell["bbox"]
        cx, cy = (x + w / 2) / w_px, (y + h / 2) / h_px
        best, best_area = None, 1e9
        for i, (bx, by, bw, bh) in enumerate(boxes):
            if bx <= cx <= bx + bw and by <= cy <= by + bh and bw * bh < best_area:
                best, best_area = i, bw * bh
        if best is not None:
            owned[best].append((h / h_px, text, strip_font((cell.get("font") or {}).get("name"))))
    h_pt = float(meta["original_height"])
    return {
        "split": split, "shard": shard, "category": meta["doc_category"], "collection": meta["collection"], "doc": meta["original_filename"],
        "page_no": meta["page_no"], "num_pages": meta["num_pages"], "w_pt": meta["original_width"], "h_pt": h_pt,
        "cells": len(cells), "chars": chars,
        "boxes": [box_record(CATEGORIES[c - 1], b, owned[i], h_pt) for i, (c, b) in enumerate(zip(row["category_id"], boxes))],
    }


def fetch_shard(args: tuple[str, int, str]) -> tuple[str, int, int]:
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    split, i, out = args
    target = Path(out) / f"{split}-{i:05d}.jsonl.gz"
    if target.exists():
        return split, i, -1
    fs = HfFileSystem()
    n = 0
    tmp = target.with_suffix(".tmp")
    with fs.open(f"{REPO}/{split}-{i:05d}-of-{SHARDS[split]:05d}.parquet", "rb") as fh, gzip.open(tmp, "wt", encoding="utf-8") as sink:
        parquet = pq.ParquetFile(fh)
        for group in range(parquet.metadata.num_row_groups):
            for row in parquet.read_row_group(group, columns=COLUMNS).to_pylist():
                sink.write(json.dumps(real_page(row, split, i), separators=(",", ":")) + "\n")
                n += 1
    tmp.replace(target)
    return split, i, n


def fetch(out: Path, splits: list[str], workers: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(s, i, str(out)) for s in splits for i in range(SHARDS[s])]
    with Pool(workers) as pool:
        for split, i, n in pool.imap_unordered(fetch_shard, jobs):
            print(f"{split} {i:02d}: {'cached' if n < 0 else f'{n} pages'}", flush=True)


def synthetic(root: Path, out: Path) -> None:
    from synthetic_pdf_bench.export.coco import BLOCK_TYPE_TO_CATEGORY
    from synthetic_pdf_bench.schema.truth import DocumentTruth

    files = sorted([*root.glob("truth/document.json"), *root.glob("*/truth/document.json")])
    with gzip.open(out, "wt", encoding="utf-8") as sink:
        for path in files:
            truth = DocumentTruth.model_validate_json(path.read_text(encoding="utf-8"))
            recipe = truth.metadata.get("base_doc_id") or truth.doc_id
            style = (truth.metadata.get("layout_style") or {}).get("font_family", "Helvetica")
            for page in truth.pages:
                w, h = page.width_pt, page.height_pt
                boxes, chars, cells = [], 0, 0
                for b in page.blocks:
                    category = BLOCK_TYPE_TO_CATEGORY.get(b.type)
                    if category is None:
                        continue
                    # PDF points, y up -> page fractions, y down
                    x0, y0, x1, y1 = b.bbox_pt
                    lines = [((ln.bbox_pt[3] - ln.bbox_pt[1]) / h, ln.text) for ln in getattr(b, "lines", None) or []]
                    text = b.text or ""
                    chars += sum(len(t) for _, t in lines) or len(text)
                    cells += len(lines)
                    font = b.metadata.get("font_family", style) + ("-Bold" if b.type in {"title", "heading"} else "")  # the renderer draws these in bold
                    cell_list = [(lh, t, font) for lh, t in lines]
                    boxes.append(box_record(category, (x0 / w, 1 - y1 / h, (x1 - x0) / w, (y1 - y0) / h), cell_list, h))
                sink.write(json.dumps({"split": "synthetic", "shard": 0, "category": truth.metadata.get("recipe_variant", "synthetic"), "collection": recipe,
                                       "doc": truth.doc_id, "page_no": page.page_index, "num_pages": len(truth.pages), "w_pt": w, "h_pt": h,
                                       "cells": cells, "chars": chars, "boxes": boxes}, separators=(",", ":")) + "\n")


def bank(survey_dir: Path, out: Path, docs_per_category: int, seed: int) -> None:
    """A compact layout bank: the train pages of `docs_per_category` seeded random documents of each category (a few hundred documents are
    plenty of layouts and keep every generator worker's memory small)."""
    import random

    by_doc: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for path in sorted(survey_dir.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                page = json.loads(line)
                if page["split"] == "train":
                    by_doc[(page["category"], page["doc"])].append(line)
    rng = random.Random(seed)
    chosen = []
    for category in sorted({c for c, _ in by_doc}):
        docs = sorted(d for c, d in by_doc if c == category)
        chosen += [(category, d) for d in rng.sample(docs, min(docs_per_category, len(docs)))]
    with gzip.open(out, "wt", encoding="utf-8") as sink:
        for key in chosen:
            sink.writelines(by_doc[key])
    print(f"{len(chosen)} documents, {sum(len(by_doc[k]) for k in chosen)} pages -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--splits", nargs="+", default=["train", "validation", "test"], choices=list(SHARDS))
    f.add_argument("--workers", type=int, default=4)
    b = sub.add_parser("bank")
    b.add_argument("survey", type=Path)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--docs-per-category", type=int, default=100)
    b.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("synthetic")
    s.add_argument("root", type=Path)
    s.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args.out, args.splits, args.workers)
    elif args.command == "bank":
        bank(args.survey, args.out, args.docs_per_category, args.seed)
    else:
        synthetic(args.root, args.out)


if __name__ == "__main__":
    sys.exit(main())
