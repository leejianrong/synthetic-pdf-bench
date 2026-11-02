"""Train/val/test assignment that keeps leakage groups together."""

from __future__ import annotations

import json
import random
from pathlib import Path

from synthetic_pdf_bench.export.coco import write_coco

SPLIT_BY = ("recipe", "template", "document")


def _group_key(document: dict, split_by: str) -> str:
    if split_by == "recipe":
        return document["recipe_path"]
    if split_by == "template":
        return json.dumps(document["metadata"]["layout_style"], sort_keys=True)
    return document["doc_id"]


def assign_splits(documents: list[dict], ratios: dict[str, float], split_by: str, seed: int) -> dict[str, list[str]]:
    """Map split name -> doc_ids. Every group (same recipe / same template) lands in exactly one split.

    With few groups the realized proportions are coarse; they are reported, not forced.
    """
    groups: dict[str, list[str]] = {}
    for document in documents:
        groups.setdefault(_group_key(document, split_by), []).append(document["doc_id"])
    wanted = [name for name, ratio in ratios.items() if ratio > 0]
    if len(groups) < len(wanted):
        raise ValueError(
            f"split_by={split_by} gives {len(groups)} groups, too few to fill {len(wanted)} splits; "
            "add recipes/templates, lower the split count, or use --split-by document (which can leak text across splits)"
        )
    total = sum(ratios.values())
    targets = {name: ratios[name] / total * len(documents) for name in wanted}
    result: dict[str, list[str]] = {name: [] for name in ratios}
    order = list(groups.values())
    random.Random(seed).shuffle(order)
    order.sort(key=len, reverse=True)  # stable: big groups first, ties keep the shuffled order
    for group in order:
        neediest = max(wanted, key=lambda name: 1 - len(result[name]) / targets[name])
        result[neediest].extend(group)
    return result


def write_coco_splits(root: Path) -> list[Path]:
    """One ``coco_<split>.json`` per split listed in ``root/splits.json``."""
    splits = json.loads((root / "splits.json").read_text(encoding="utf-8"))["splits"]
    return [write_coco(root, root / f"coco_{name}.json", doc_ids=set(ids)) for name, ids in splits.items() if ids]
