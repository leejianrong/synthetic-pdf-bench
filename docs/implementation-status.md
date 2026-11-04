# Implementation Status

## Overview

`synthetic-pdf-bench` is a scene-graph-first synthetic PDF generator for benchmarking PDF-to-Markdown and structured document extraction pipelines. Ground truth is created before rendering and exported directly from the planned scene graph rather than recovered by parsing the generated PDF.

## What Is Implemented

### Core generation pipeline

- Recipe-driven document generation with deterministic seeds
- Scene graph with page and block truth
- ReportLab PDF rendering
- PyMuPDF page rasterization
- Figure crop extraction
- Markdown and JSON truth export

### Layout engine

- One-column and two-column flow
- Metric-based text height estimation using ReportLab font metrics
- Repeated headers, footers, and page numbers
- Section page-break hints
- Paragraphs, lists (one box per item), tables, figures, captions, footnotes (page-bottom), display formulas, and references; the `structured` variant derives lists, footnotes and formulas from recipe text
- Table splitting across columns and pages
- Caption placement before or after figures and tables
- Page-level overlap and bounds validation

### Figures and tables

- ReportLab vector figures for diagrams and placeholders
- Matplotlib raster backend for:
  - bar charts
  - line charts
  - stacked bar charts
  - timelines
  - scatter plots
  - heatmaps
- Table variants for:
  - narrow tables
  - wide tables
  - numeric tables
  - multilingual tables
  - wrapped cell text
  - merged cells with real rowspan/colspan
  - multi-page long tables

### Dataset and evaluation

- COCO layout export (`export-coco`) with DocLayNet-style classes and reading order
- Table-structure export (`export-tables`): PubTabNet-style JSONL with spans and cell boxes
- Docling layout baseline on 500 real DocLayNet pages: [layout-baselines.md](layout-baselines.md)
- Layout training and eval script (`scripts/train_layout.py`): YOLOX-Tiny fine-tune with per-class mAP, rehearsed on CPU
- YOLO (`export-yolo`) and Hugging Face imagefolder (`export-hf`) exports that follow the splits

- Single-document generation
- Batch dataset generation with dataset manifest
- Recipe/layout variants
- Per-document quality report
- Dataset-level summary stats
- Evaluator for parser outputs
- Dummy parser that copies truth into prediction format for smoke testing
- Scan degradation (`--degrade`), parallel generation (`--workers`) and leakage-safe splits (`--splits`, `--split-by`)
- Table metrics: TEDS, including spans
- Research notes on DocLayNet and Docling: [research/doclaynet-docling-spike.md](research/doclaynet-docling-spike.md)

## Current Repository Structure

### Runtime recipes

Canonical runtime inputs live in:

```text
data/recipes/canonical/
```

Six Southeast Asian history recipes (`sea_historical_report_v1`, `indonesia_colonial_nationalist_origins_v1`, `malaya_malaysia_state_formation_v1`, `malaysia_history_1900_post_2018_v1`, `singapore_history_1900_2020s_v1`, `singapore_malaysia_1963_1965_v1`) and `visual_benchmark_v1` (charts and table shapes). All share one subject area, so content variety is thin; see [roadmap.md](roadmap.md).

### Research and enrichment artifacts

Intermediate recipe-building materials live in:

```text
data/recipes/research/
```

Current research workspace:

```text
data/recipes/research/sea_historical_report_v1/
  report_outline.json
  prose_blocks.json
  tables.json
  vector_figures.json
```

## Current Limitations

- Only report-style documents from history recipes; no invoices, forms, slides or academic layouts
- Degradation is flat-scan only (skew, shift, contrast, blur, noise, JPEG): no perspective, curl or rotated pages
- No word or text-line boxes in the truth, so OCR models cannot be trained from it yet
- No benchmark runner that executes a parser across a whole dataset, and reading order is scored only for blocks that carry our `block_id`
- Models trained on synthetic pages alone do not transfer to real pages (0.025 mAP50-95 vs 0.463 from 2,000 real pages): [layout-baselines.md](layout-baselines.md)
- No image-based visual diff checks beyond nonblank smoke validation

## Next steps

See [roadmap.md](roadmap.md) for the plan and the Pandan board (SYN) for the cards.
