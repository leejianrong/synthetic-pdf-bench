"""Table-structure export in the PubTabNet layout used by table-structure models (TableFormer and similar).

One JSON line per table segment: the page image, the table box in page pixels, HTML structure
tokens with row/column spans, and one entry per cell with character tokens and its pixel box.
"""

from __future__ import annotations

import json
from itertools import groupby
from pathlib import Path

from synthetic_pdf_bench.schema.blocks import TableBlock
from synthetic_pdf_bench.schema.truth import DocumentTruth


def table_record(table: TableBlock, doc_id: str, filename: str) -> dict:
    tokens: list[str] = ["<thead>"]
    for row, cells in groupby(table.cells, key=lambda c: c.row):  # cells are stored row-major
        if row == 1:
            tokens += ["</thead>", "<tbody>"]
        tokens.append("<tr>")
        for cell in cells:
            attrs = [f' {name}="{n}"' for name, n in (("rowspan", cell.rowspan), ("colspan", cell.colspan)) if n > 1]
            tokens += ["<td", *attrs, ">", "</td>"] if attrs else ["<td>", "</td>"]
        tokens.append("</tr>")
    tokens.append("</tbody>")
    return {
        "doc_id": doc_id,
        "table_id": table.table_id,
        "page_index": table.page_index,
        "filename": filename,
        "bbox": table.bbox_px,
        "html": {
            "structure": {"tokens": tokens},
            "cells": [{"tokens": list(c.text), "bbox": c.bbox_px} for c in table.cells],
        },
    }


def write_table_structure(root: Path, output: Path | None = None, doc_ids: set[str] | None = None) -> Path:
    """Write ``tables.jsonl`` for every ``truth/document.json`` at or directly under ``root``."""
    truth_files = sorted([*root.glob("truth/document.json"), *root.glob("*/truth/document.json")])
    if not truth_files:
        raise FileNotFoundError(f"no truth/document.json found under {root}")
    output = output or root / "tables.jsonl"
    lines = []
    for truth_file in truth_files:
        truth = DocumentTruth.model_validate_json(truth_file.read_text(encoding="utf-8"))
        if doc_ids is not None and truth.doc_id not in doc_ids:
            continue
        doc_dir = truth_file.parent.parent
        for table in truth.tables:
            image = truth.pages[table.page_index].rendered_image
            filename = (doc_dir / image.image_path).relative_to(root).as_posix()
            lines.append(json.dumps(table_record(table, truth.doc_id, filename), ensure_ascii=False))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
