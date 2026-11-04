"""Compare class mix and boxes per page of COCO layout exports with DocLayNet's published mix (paper Table 1).

    python scripts/layout_stats.py synthetic=output/corpus/coco_train.json real=data_real/coco_test.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

# DocLayNet paper Table 1: boxes per class, 1,107,470 in all.
DOCLAYNET_BOXES = {"text": 510377, "list-item": 185660, "section-header": 142884, "page-footer": 70878, "page-header": 58022, "picture": 45976,
                   "table": 34733, "formula": 25027, "caption": 22524, "footnote": 6318, "title": 5071}
DOCLAYNET_PAGES = 91104  # annotation instances over 80,863 pages (paper section 3)


def class_mix(path: Path) -> tuple[dict[str, int], int]:
    coco = json.loads(path.read_text())
    names = {c["id"]: c["name"] for c in coco["categories"]}
    counts = collections.Counter(names[a["category_id"]].lower() for a in coco["annotations"])
    return dict(counts), len(coco["images"])


def report(sets: dict[str, tuple[dict[str, int], int]]) -> str:
    total = sum(DOCLAYNET_BOXES.values())
    columns = {"DocLayNet": (DOCLAYNET_BOXES, DOCLAYNET_PAGES), **sets}
    lines = ["| class | " + " | ".join(columns) + " |", "|---|" + "---:|" * len(columns)]
    for name in sorted(DOCLAYNET_BOXES, key=DOCLAYNET_BOXES.get, reverse=True):
        cells = [f"{100 * counts.get(name, 0) / (sum(counts.values()) or 1):.1f}%" for counts, _ in columns.values()]
        lines.append(f"| {name.capitalize()} | " + " | ".join(cells) + " |")
    lines.append("| **boxes per page** | " + " | ".join(f"{sum(c.values()) / max(pages, 1):.1f}" for c, pages in columns.values()) + " |")
    assert total == 1107470
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sets", nargs="+", metavar="LABEL=COCO_JSON")
    a = p.parse_args()
    print(report({label: class_mix(Path(path)) for label, path in (s.split("=", 1) for s in a.sets)}))


if __name__ == "__main__":
    main()
