# Implementation Status

## Overview

`synthetic_pdf_bench` is a scene-graph-first synthetic PDF generator for benchmarking PDF-to-Markdown and structured document extraction pipelines. Ground truth is created before rendering and exported directly from the planned scene graph rather than recovered by parsing the generated PDF.

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
- Paragraphs, lists, tables, figures, captions, footnotes, and references
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
  - merged-cell approximations
  - multi-page long tables

### Dataset and evaluation

- Single-document generation
- Batch dataset generation with dataset manifest
- Recipe/layout variants
- Per-document quality report
- Dataset-level summary stats
- Evaluator for parser outputs
- Dummy parser that copies truth into prediction format for smoke testing

## Current Repository Structure

### Runtime recipes

Canonical runtime inputs live in:

```text
data/recipes/canonical/
```

Current canonical recipes:

- `sea_historical_report_v1.json`
- `visual_benchmark_v1.json`

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

- No dedicated recipe validation CLI yet
- No benchmark runner that executes a parser across a whole dataset automatically
- No document-family templates beyond the current report-style flows
- No OCR/noise/degradation simulation yet
- No image-based visual diff checks beyond nonblank smoke validation
- No advanced table semantics beyond merged-cell approximation metadata
- No parser-side aggregation report for multi-document evaluation runs

## Recommended Next Steps

### Highest value

- Build a small benchmark runner that loops over a dataset, invokes a parser, and aggregates evaluation outputs
- Add more canonical recipes across distinct document families
- Add parser-run summary metrics across a whole dataset

### Generator expansion

- Add recipe families for academic papers, policy briefs, annual reports, manuals, and semi-structured government documents
- Add more realistic bibliography/reference layouts
- Add callouts, sidebars, multi-figure pages, and denser footnote patterns
- Add noise and degradation options as explicit generation profiles

### Evaluation expansion

- Add block-type confusion summaries
- Add page-level scorecards
- Add document-level pass/fail thresholds
- Add dataset-wide leaderboard-style aggregation

### Workflow hardening

- Add a dedicated recipe validation command
- Add release/versioning conventions for benchmark datasets
- Add documentation for benchmark dataset versioning and parser result storage
