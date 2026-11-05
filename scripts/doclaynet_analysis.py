"""Compare survey records of DocLayNet and of our synthetic pages (see doclaynet_survey.py).

    python scripts/doclaynet_analysis.py --real output/doclaynet/survey --synthetic output/doclaynet/survey_synthetic.jsonl.gz \
        --out output/doclaynet/analysis.json

Computes the same page-level and box-level measures for each corpus (and for each DocLayNet document category), then ranks the
differences with the Kolmogorov-Smirnov distance (0 identical, 1 disjoint). Quantiles are reported next to it so the size of a gap can be read.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import itertools
import json
import re
from pathlib import Path

import numpy as np

CATEGORIES = ["caption", "footnote", "formula", "list-item", "page-footer", "page-header", "picture", "section-header", "table", "text", "title"]
FAMILIES = [("latex", r"^(cm|sf|lm)(r|bx|ti|mi|sy|ex|ss|tt|csc|sl)\d*|computer ?modern|latin ?modern"), ("dejavu", r"dejavu|bitstream vera"), ("mono", r"courier|mono|consolas|typewriter"), ("times", r"times|liberation ?serif|nimbusrom|tinos"),
            ("helvetica", r"helvetica|arial|liberation ?sans|nimbussan|arimo"), ("calibri", r"calibri|carlito"),
            ("serif-other", r"cambria|georgia|garamond|palatino|bookman|century|minion|baskerville|serif|roman|book antiqua"),
            ("sans-other", r"verdana|tahoma|segoe|myriad|frutiger|futura|gill|univers|lato|open ?sans|roboto|sans|gothic|din")]
TEXT_CLASSES = {"text", "list-item"}


def family(font: str | None) -> str:
    if not font:
        return "none"
    low = font.lower()
    for name, pattern in FAMILIES:
        if re.search(pattern, low):
            return name
    return "other"


def read_pages(source: Path):
    files = sorted(source.glob("*.jsonl.gz")) if source.is_dir() else [source]
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)


def columns_of(boxes: list[list]) -> int:
    """Text columns on a page: clusters of text-box centres along x, among boxes narrower than 0.7 of the page; 0 if under 3 text boxes."""
    centres = sorted(b[1] + b[3] / 2 for b in boxes if b[0] in TEXT_CLASSES and b[3] < 0.7)
    if sum(1 for b in boxes if b[0] in TEXT_CLASSES) < 3:
        return 0
    if not centres:
        return 1
    clusters = 1 + sum(1 for a, b in itertools.pairwise(centres) if b - a > 0.12)
    return min(clusters, 3)


def coverage_of(boxes: list[list], grid: int = 40) -> float:
    mask = np.zeros((grid, grid), dtype=bool)
    for b in boxes:
        x0, y0 = int(max(b[1], 0) * grid), int(max(b[2], 0) * grid)
        x1, y1 = int(np.ceil(min(b[1] + b[3], 1) * grid)), int(np.ceil(min(b[2] + b[4], 1) * grid))
        mask[y0:y1, x0:x1] = True
    return float(mask.mean())


def nested_pairs(boxes: list[list]) -> int:
    """Pairs where one box lies at least 80% inside another (text inside a picture or table, a caption inside a figure)."""
    count = 0
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if i == j:
                continue
            ix = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
            iy = max(0.0, min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2]))
            small = a[3] * a[4]
            if small > 0 and ix * iy / small >= 0.8 and a[3] * a[4] <= b[3] * b[4]:
                count += 1
    return count


def gaps_below(boxes: list[list], h_pt: float) -> list[float]:
    """Vertical gap in points from each box to the nearest box below it that shares at least half of the narrower box's width."""
    out = []
    for a in boxes:
        bottom, best = a[2] + a[4], None
        for b in boxes:
            overlap = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            if b is not a and b[2] >= bottom - 0.004 and overlap >= 0.5 * min(a[3], b[3]) and (best is None or b[2] < best):
                best = b[2]
        if best is not None:
            out.append(max(best - bottom, 0.0) * h_pt)
    return out


def partial_overlaps(boxes: list[list]) -> int:
    """Pairs that overlap by 5% to 80% of the smaller box, i.e. touching or crossing without nesting."""
    count = 0
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            ix = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
            iy = max(0.0, min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2]))
            small = min(a[3] * a[4], b[3] * b[4])
            if small > 0 and 0.05 <= ix * iy / small < 0.8:
                count += 1
    return count


class Corpus:
    def __init__(self) -> None:
        self.pages: dict[str, list[float]] = collections.defaultdict(list)
        self.boxes: dict[str, dict[str, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
        self.class_pages: dict[str, int] = collections.Counter()
        self.class_boxes: dict[str, int] = collections.Counter()
        self.fonts: dict[str, int] = collections.Counter()
        self.bold: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        self.docs: set[str] = set()
        self.collections: set[str] = set()
        self.page_sizes: dict[str, int] = collections.Counter()
        self.gaps: list[float] = []
        self.n = 0

    def add(self, page: dict) -> None:
        boxes = page["boxes"]
        self.n += 1
        self.docs.add(page["doc"])
        self.collections.add(page["collection"])
        w_pt, h_pt = page["w_pt"], page["h_pt"]
        self.page_sizes["letter" if abs(w_pt - 612) < 4 and abs(h_pt - 792) < 4 else "a4" if abs(w_pt - 595) < 4 and abs(h_pt - 842) < 4 else "other"] += 1
        p = self.pages
        p["boxes_per_page"].append(len(boxes))
        p["classes_per_page"].append(len({b[0] for b in boxes}))
        p["coverage"].append(coverage_of(boxes))
        p["top_margin"].append(min((b[2] for b in boxes), default=0))
        p["bottom_margin"].append(1 - max((b[2] + b[4] for b in boxes), default=1))
        p["left_margin"].append(min((b[1] for b in boxes), default=0))
        p["right_margin"].append(1 - max((b[1] + b[3] for b in boxes), default=1))
        p["columns"].append(columns_of(boxes))
        p["nested_pairs"].append(nested_pairs(boxes))
        p["partial_overlaps"].append(partial_overlaps(boxes))
        p["landscape"].append(int(h_pt < w_pt))
        p["chars_per_page"].append(page["chars"])
        self.gaps.extend(gaps_below(boxes, h_pt))
        p["aspect_h_over_w"].append(h_pt / w_pt)
        p["fonts_per_page"].append(len({family(b[8]) for b in boxes if b[8]}))
        for name in {b[0] for b in boxes}:
            self.class_pages[name] += 1
        for name in CATEGORIES:
            p[f"count_{name}"].append(sum(1 for b in boxes if b[0] == name))
        for c, x, y, w, h, cells, chars, cell_h, font in boxes:
            self.class_boxes[c] += 1
            d = self.boxes[c]
            d["width"].append(w)
            d["height"].append(h)
            d["area"].append(w * h)
            d["aspect_w_over_h"].append((w * w_pt) / max(h * h_pt, 1e-6))
            d["cx"].append(x + w / 2)
            d["cy"].append(y + h / 2)
            if cells:
                d["chars"].append(chars)
                d["cells"].append(cells)
            if cell_h:
                d["text_height_pt"].append(cell_h)
            if font:
                fam = family(font)
                self.fonts[fam] += 1
                low = font.lower()
                self.bold[c][0] += int(bool(re.search(r"bold|black|heavy|semibold|demi|^(cm|sf)bx", low)))
                self.bold[c][1] += 1


def quantiles(values: list[float]) -> list[float] | None:
    return [round(float(q), 4) for q in np.quantile(values, [0.1, 0.5, 0.9])] if len(values) >= 5 else None


def ks(a: list[float], b: list[float]) -> float | None:
    if len(a) < 5 or len(b) < 5:
        return None
    a, b = np.sort(a), np.sort(b)
    grid = np.concatenate([a, b])
    return round(float(np.max(np.abs(np.searchsorted(a, grid, side="right") / len(a) - np.searchsorted(b, grid, side="right") / len(b)))), 3)


def summarize(c: Corpus) -> dict:
    return {
        "pages": c.n, "documents": len(c.docs), "collections": len(c.collections), "page_sizes": dict(c.page_sizes),
        "class_boxes": dict(c.class_boxes), "class_page_share": {k: round(v / c.n, 4) for k, v in c.class_pages.items()},
        "font_families": dict(c.fonts), "bold_share": {k: round(v[0] / v[1], 3) for k, v in c.bold.items() if v[1]},
        "page": {k: quantiles(v) for k, v in c.pages.items()}, "gap_below_pt": quantiles(c.gaps),
        "page_mean": {k: round(float(np.mean(v)), 4) for k, v in c.pages.items()},
        "box": {cls: {k: quantiles(v) for k, v in d.items()} for cls, d in c.boxes.items()},
    }


def compare(real: Corpus, syn: Corpus) -> list[dict]:
    rows = []
    for k, v in real.pages.items():
        rows.append({"metric": f"page.{k}", "ks": ks(v, syn.pages.get(k, [])), "real": quantiles(v), "synthetic": quantiles(syn.pages.get(k, []))})
    rows.append({"metric": "page.gap_below_pt", "ks": ks(real.gaps, syn.gaps), "real": quantiles(real.gaps), "synthetic": quantiles(syn.gaps)})
    for cls in CATEGORIES:
        for k, v in real.boxes[cls].items():
            s = syn.boxes[cls].get(k, [])
            rows.append({"metric": f"{cls}.{k}", "ks": ks(v, s), "real": quantiles(v), "synthetic": quantiles(s), "n_real": len(v), "n_syn": len(s)})
    return sorted((r for r in rows if r["ks"] is not None), key=lambda r: -r["ks"]) + [r for r in rows if r["ks"] is None]


def figures(real: Corpus, by_category: dict[str, Corpus], syn: Corpus, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    blue, orange = "#2a6fbb", "#d9822b"
    order = sorted(CATEGORIES, key=lambda c: -real.class_pages[c])

    fig, ax = plt.subplots(figsize=(7, 4.2))
    y = np.arange(len(order))
    ax.barh(y - 0.2, [100 * real.class_pages[c] / real.n for c in order], 0.4, color=blue, label="DocLayNet (80,863 pages)")
    ax.barh(y + 0.2, [100 * syn.class_pages[c] / syn.n for c in order], 0.4, color=orange, label="Synthetic (2,962 pages)")
    ax.set_yticks(y, order)
    ax.invert_yaxis()
    ax.set_xlabel("% of pages that contain at least one box of the class")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "class_presence.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.3))
    for ax, key, label, cap in zip(axes, ["chars_per_page", "coverage", "classes_per_page"], ["Characters per page", "Share of page covered by boxes", "Distinct classes per page"], [8000, 1, 11]):
        for corpus, colour, name in ((real, blue, "DocLayNet"), (syn, orange, "Synthetic")):
            v = np.sort(np.clip(corpus.pages[key], 0, cap))
            ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=colour, label=name)
        ax.set_xlabel(label)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Share of pages at or below")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "page_density.png", dpi=150)
    plt.close(fig)

    palette = ["#2a6fbb", "#6fa8dc", "#3d9970", "#7fbf7b", "#d9822b", "#f2b97c", "#8e6bbf", "#c9a0dc", "#b04a4a", "#888888", "#222222"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    rows = [(k.replace("_", " "), v) for k, v in by_category.items()] + [("synthetic", syn)]
    left = np.zeros(len(rows))
    for colour, cls in zip(palette, ["text", "list-item", "section-header", "page-footer", "page-header", "picture", "table", "formula", "caption", "footnote", "title"]):
        share = np.array([100 * v.class_boxes[cls] / sum(v.class_boxes.values()) for _, v in rows])
        ax.barh([n for n, _ in rows], share, left=left, color=colour, label=cls)
        left += share
    ax.invert_yaxis()
    ax.set_xlabel("% of boxes")
    ax.legend(frameon=False, ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.45, -0.18))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "category_mix.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--figures", type=Path, help="also write the report figures to this directory")
    args = parser.parse_args()

    real, by_category, syn = Corpus(), collections.defaultdict(Corpus), Corpus()
    for page in read_pages(args.real):
        real.add(page)
        by_category[page["category"]].add(page)
    for page in read_pages(args.synthetic):
        syn.add(page)
    result = {"real": summarize(real), "synthetic": summarize(syn), "real_by_category": {k: summarize(v) for k, v in sorted(by_category.items())},
              "gaps": compare(real, syn), "gaps_by_category": {k: compare(v, syn)[:25] for k, v in sorted(by_category.items())}}
    args.out.write_text(json.dumps(result, indent=1))
    if args.figures:
        figures(real, by_category, syn, args.figures)
    print(f"real pages {real.n}, synthetic pages {syn.n}; wrote {args.out}")


if __name__ == "__main__":
    main()
