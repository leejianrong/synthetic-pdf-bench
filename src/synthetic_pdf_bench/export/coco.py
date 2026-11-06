"""COCO layout-detection export with DocLayNet-style classes and reading order."""

from __future__ import annotations

import json
from pathlib import Path

from synthetic_pdf_bench.schema.truth import DocumentTruth

CATEGORIES = [
    "caption",
    "footnote",
    "formula",
    "list-item",
    "page-footer",
    "page-header",
    "picture",
    "section-header",
    "table",
    "text",
    "title",
]
_CATEGORY_IDS = {name: i for i, name in enumerate(CATEGORIES, start=1)}

# Block types emitted by the generators -> layout class.
BLOCK_TYPE_TO_CATEGORY = {
    "caption": "caption",
    "figure": "picture",
    "footer": "page-footer",
    "footnote": "footnote",
    "formula": "formula",
    "header": "page-header",
    "heading": "section-header",
    "list_item": "list-item",
    "page_number": "page-footer",
    "paragraph": "text",
    "reference": "list-item",  # real bibliographies are annotated one list item per entry
    "table": "table",
    "title": "title",
}


def export_coco(root: Path, doc_ids: set[str] | None = None) -> dict:
    """Build a COCO dict for every ``truth/document.json`` at or directly under ``root``.

    ``doc_ids`` keeps only those documents.

    ``file_name`` is relative to ``root``. ``reading_order`` is the block's rank within
    its page, an extra field on each annotation.
    """
    truth_files = sorted([*root.glob("truth/document.json"), *root.glob("*/truth/document.json")])
    if not truth_files:
        raise FileNotFoundError(f"no truth/document.json found under {root}")

    images, annotations = [], []
    for truth_file in truth_files:
        truth = DocumentTruth.model_validate_json(truth_file.read_text(encoding="utf-8"))
        if doc_ids is not None and truth.doc_id not in doc_ids:
            continue
        doc_dir = truth_file.parent.parent
        for page in truth.pages:
            rendered = page.rendered_image
            if rendered is None or rendered.width_px is None or rendered.height_px is None:
                raise ValueError(f"{truth.doc_id} page {page.page_index} has no rendered image")
            image_id = len(images) + 1
            images.append(
                {
                    "id": image_id,
                    "file_name": (doc_dir / rendered.image_path).relative_to(root).as_posix(),
                    "width": rendered.width_px,
                    "height": rendered.height_px,
                    "doc_id": truth.doc_id,
                    "page_index": page.page_index,
                }
            )
            ordered = sorted(page.blocks, key=lambda b: b.reading_order)
            for rank, block in enumerate(ordered):
                x0, y0, x1, y1 = block.bbox_px or _pt_to_px(block.bbox_pt, rendered.dpi)
                annotations.append(
                    {
                        "id": len(annotations) + 1,
                        "image_id": image_id,
                        "category_id": _CATEGORY_IDS[BLOCK_TYPE_TO_CATEGORY[block.type]],
                        "bbox": [x0, y0, x1 - x0, y1 - y0],
                        "area": (x1 - x0) * (y1 - y0),
                        "iscrowd": 0,
                        "reading_order": rank,
                    }
                )

    return {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": i, "name": name} for name, i in _CATEGORY_IDS.items()],
    }


def write_coco(root: Path, output: Path | None = None, doc_ids: set[str] | None = None) -> Path:
    output = output or root / "coco.json"
    output.write_text(json.dumps(export_coco(root, doc_ids), indent=2), encoding="utf-8")
    return output


def _pt_to_px(bbox_pt: list[float], dpi: int) -> list[float]:
    scale = dpi / 72
    return [v * scale for v in bbox_pt]
