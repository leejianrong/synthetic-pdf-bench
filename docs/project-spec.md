# Synthetic PDF Benchmark Generator — Project Specification

## 1. Project Goal

Build a Python-based synthetic PDF generation and benchmarking framework for evaluating PDF-to-Markdown pipelines.

The framework generates synthetic PDFs together with deterministic ground truth for:

* Markdown reconstruction
* Text block extraction
* Table extraction
* Figure/image extraction
* Figure location metadata
* Figure-to-Markdown linking
* Page-level rendered images
* Optional future model-training annotations

The generator must produce ground truth at document creation time. It must not rely on downstream PDF parsers to infer the true layout.

The primary target use case is evaluating systems that take an original PDF as input and output:

```text
document.md
figures/*.png
metadata.json
```

where the Markdown contains references to extracted figures, and the metadata links those figures to their page locations.

---

## 2. Core Design Principle

The project should use a **scene graph first** architecture.

Instead of drawing a PDF and then trying to recover coordinates, the generator should:

```text
Create semantic document recipe
        ↓
Plan exact layout boxes
        ↓
Build a scene graph with coordinates
        ↓
Render scene graph to PDF
        ↓
Export Markdown and JSON ground truth from the same scene graph
        ↓
Rasterize PDF pages and crop ground-truth figures
```

ReportLab should be used as a renderer, not as the source of layout truth.

---

## 3. Primary Outputs

For every generated document, the system should produce:

```text
output/
  synthetic_000001/
    document.pdf
    truth/
      document.json
      document.md
      pages/
        page_001.png
        page_002.png
      figures/
        fig_001.png
        fig_002.png
```

### 3.1 `document.pdf`

The synthetic PDF consumed by the benchmarked pipeline.

### 3.2 `truth/document.md`

The canonical Markdown representation of all non-image content, including figure references.

Example:

```md
# Synthetic Technical Report

This report evaluates a multilingual document processing pipeline.

![Figure 1: System architecture](figures/fig_001.png)

*Figure 1: System architecture.*

| Region | Revenue |
|---|---:|
| Singapore | 120.5 |
| Indonesia | 98.3 |
```

### 3.3 `truth/document.json`

The canonical structured ground truth.

It should include:

* document metadata
* generation seed
* language profile
* page sizes
* rendered page image paths
* block-level bounding boxes
* table-level data
* table-cell bounding boxes
* figure metadata
* figure PNG paths
* Markdown spans
* figure-to-caption links
* figure-to-Markdown links

### 3.4 `truth/pages/*.png`

Rendered page images, generated from the final PDF using a canonical renderer.

Recommended default: PyMuPDF.

### 3.5 `truth/figures/*.png`

Ground-truth figure crops, created by rasterizing/cropping the final rendered PDF page region corresponding to each figure block.

This is important because figures may be raster, vector, or hybrid.

---

## 4. Ground Truth Levels

The first version should support the following mandatory ground-truth levels:

### 4.1 Block-level boxes

Every semantic document block should have a bounding box.

Mandatory block types:

```text
title
author
abstract
heading
paragraph
list
list_item
table
figure
caption
header
footer
page_number
footnote
reference
```

Each block should include:

```json
{
  "block_id": "b000001",
  "type": "paragraph",
  "page_index": 0,
  "reading_order": 3,
  "bbox_pt": [72, 600, 540, 660],
  "bbox_px": [300, 550, 2250, 800],
  "bbox_norm": [0.1176, 0.7575, 0.8823, 0.8333],
  "text": "This is an example paragraph.",
  "markdown": "This is an example paragraph.",
  "markdown_span": [38, 72],
  "include_in_markdown": true,
  "language": "en"
}
```

### 4.2 Table-cell boxes

Every table should include cell-level structure.

Each table should include:

```json
{
  "table_id": "tbl_001",
  "block_id": "b000010",
  "page_index": 1,
  "bbox_pt": [72, 300, 540, 500],
  "markdown": "| Metric | Value |\n|---|---:|\n| Accuracy | 0.94 |",
  "html": "<table>...</table>",
  "matrix": [
    ["Metric", "Value"],
    ["Accuracy", "0.94"]
  ],
  "cells": [
    {
      "cell_id": "cell_001",
      "row": 0,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "text": "Metric",
      "bbox_pt": [72, 470, 306, 500],
      "bbox_px": [300, 1217, 1275, 1342],
      "is_header": true
    }
  ]
}
```

### 4.3 Figure boxes

Each figure should include:

```json
{
  "figure_id": "fig_001",
  "block_id": "b000020",
  "page_index": 2,
  "kind": "flowchart",
  "source_type": "vector",
  "bbox_pt": [120, 320, 492, 590],
  "bbox_px": [500, 842, 2050, 1967],
  "png_path": "truth/figures/fig_001.png",
  "caption_block_id": "b000021",
  "markdown_ref": "![Figure 1: System architecture](figures/fig_001.png)",
  "markdown_span": [500, 560]
}
```

Supported figure source types:

```text
raster
vector
hybrid
```

### 4.4 Optional future levels

The schema should be extensible to support:

```text
line boxes
word boxes
character boxes
COCO export
DocBank-style token labels
OCR-oriented annotations
```

These are not required for the MVP.

---

## 5. Coordinate System

PDF coordinates should be canonical.

### 5.1 Canonical coordinates

```text
bbox_pt = [x0, y0, x1, y1]
origin = bottom-left
unit = points
```

### 5.2 Pixel coordinates

Pixel coordinates should be derived from points at a specified DPI.

```text
bbox_px = [x0, y0, x1, y1]
origin = top-left
unit = pixels
```

### 5.3 Normalized coordinates

Normalized coordinates should also be stored for future model training.

```text
bbox_norm = [x0 / page_width, y0 / page_height, x1 / page_width, y1 / page_height]
```

### 5.4 Required coordinate utilities

Implement:

```python
pt_to_px_bbox(bbox_pt, page_height_pt, dpi)
px_to_pt_bbox(bbox_px, page_height_pt, dpi)
pt_to_norm_bbox(bbox_pt, page_width_pt, page_height_pt)
norm_to_pt_bbox(bbox_norm, page_width_pt, page_height_pt)
bbox_iou(box_a, box_b)
```

---

## 6. Markdown Requirements

Markdown should be generated from the scene graph, not extracted from the rendered PDF.

Every Markdown-included block should have:

```json
{
  "markdown": "...",
  "markdown_span": [start_char, end_char],
  "include_in_markdown": true
}
```

Figure blocks should appear in Markdown using deterministic image references:

```md
![Figure 1: System architecture](figures/fig_001.png)

*Figure 1: System architecture.*
```

Tables should be emitted as GitHub-Flavored Markdown where possible.

For complex tables, store both Markdown and HTML. Markdown may be approximate for tables with rowspans or colspans, but the JSON matrix and HTML should remain canonical.

---

## 7. Multilingual Support

The generator should support:

```text
English
Simplified Chinese
Bahasa Melayu
Bahasa Indonesia
```

### 7.1 Encoding

All files must be UTF-8.

### 7.2 Fonts

The project should support configurable fonts.

Recommended font categories:

```text
latin_serif
latin_sans
latin_mono
cjk_sans
cjk_serif
```

The code should not hardcode machine-specific font paths. It should allow font paths to be configured.

### 7.3 Text wrapping

Text wrapping should support:

* Latin word wrapping
* Chinese character-aware wrapping
* mixed-language paragraphs
* measured wrapping based on actual font metrics

For MVP, it is acceptable to implement simple deterministic wrapping with clear limitations documented.

---

## 8. Document Families

The generator should eventually support these document families:

### 8.1 Academic papers

Features:

* title
* authors
* abstract
* two-column layout
* headings
* subsections
* references
* figures
* tables
* captions

### 8.2 White papers

Features:

* long-form prose
* one-column or mixed layout
* large diagrams
* sidebars
* pull quotes
* infographics
* executive summaries

### 8.3 Long reports

Features:

* 100+ pages
* table of contents
* repeated headers and footers
* appendices
* many figures
* many tables
* page numbers
* cross-references

### 8.4 Multilingual regional reports

Features:

* primarily English text
* Chinese excerpts
* Malay and Indonesian paragraphs
* multilingual captions
* multilingual tables

---

## 9. MVP Scope

The first working milestone should generate controlled synthetic documents with:

```text
3–8 pages
headings
paragraphs
bullet lists
simple tables
basic table-cell boxes
raster figures
vector figures
captions
headers
footers
page numbers
English text
some Chinese / Malay / Indonesian text
```

The MVP should output:

```text
document.pdf
truth/document.json
truth/document.md
truth/pages/page_001.png
truth/figures/fig_001.png
```

The MVP does not need:

```text
perfect typography
full Platypus support
complex rowspans
word-level boxes
character-level boxes
100-page documents
advanced degradation
model training export
```

---

## 10. Recommended Python Package Structure

```text
synthetic-pdf-bench/
  pyproject.toml
  README.md
  src/
    synthetic_pdf_bench/
      __init__.py

      schema/
        __init__.py
        truth.py
        blocks.py

      layout/
        __init__.py
        coordinates.py
        scene.py
        simple_layout.py
        reading_order.py

      render/
        __init__.py
        reportlab_renderer.py
        pymupdf_rasterizer.py
        crops.py

      generators/
        __init__.py
        recipes.py
        text_content.py
        tables.py
        figures.py

      markdown/
        __init__.py
        writer.py

      evaluation/
        __init__.py
        bbox.py
        normalize_markdown.py
        text_metrics.py
        table_metrics.py
        figure_metrics.py

      cli/
        __init__.py
        generate.py

  tests/
    test_coordinates.py
    test_markdown_writer.py
    test_schema_serialization.py
    test_basic_generation.py

  examples/
    generate_mvp.py

  assets/
    fonts/
    raster_figures/
```

---

## 11. Core Data Models

Use Python dataclasses or Pydantic models.

Recommended models:

```python
DocumentTruth
PageTruth
Block
TextBlock
TableBlock
TableCell
FigureBlock
RenderedPage
MarkdownDocument
```

### 11.1 `DocumentTruth`

Fields:

```text
doc_id
seed
source_pdf
language_profile
pages
blocks
tables
figures
markdown_path
metadata
```

### 11.2 `PageTruth`

Fields:

```text
page_index
page_number
width_pt
height_pt
rotation
rendered_image
blocks
```

### 11.3 `Block`

Fields:

```text
block_id
type
subtype
page_index
reading_order
bbox_pt
bbox_px
bbox_norm
text
markdown
markdown_span
include_in_markdown
language
metadata
```

### 11.4 `TableBlock`

Fields:

```text
table_id
block_id
page_index
bbox_pt
bbox_px
matrix
markdown
html
cells
```

### 11.5 `FigureBlock`

Fields:

```text
figure_id
block_id
page_index
kind
source_type
bbox_pt
bbox_px
png_path
caption_block_id
markdown_ref
markdown_span
metadata
```

---

## 12. Rendering Strategy

Use ReportLab canvas directly for the MVP.

The renderer should support:

```text
draw_text_block
draw_heading
draw_paragraph
draw_table
draw_raster_figure
draw_vector_figure
draw_caption
draw_header_footer
```

The renderer should draw from already-planned coordinates.

It should not be responsible for deciding the layout.

---

## 13. Rasterization and Figure Cropping

Use PyMuPDF as the default canonical rasterizer.

Required functionality:

```python
render_pdf_pages(pdf_path, output_dir, dpi=300)
crop_figure_from_page(page_png_path, bbox_px, output_path)
```

Figure crops should be generated from the rendered PDF page so that raster, vector, and hybrid figures are treated consistently.

---

## 14. Evaluation Metrics

The first evaluation layer should support:

### 14.1 Markdown accuracy

* Character Error Rate
* normalized Markdown similarity
* heading match
* caption match

### 14.2 Table accuracy

* table count precision / recall
* row count accuracy
* column count accuracy
* cell text accuracy
* table Markdown similarity

### 14.3 Figure accuracy

* figure count precision / recall
* figure bounding-box IoU
* crop similarity, optional
* caption association accuracy
* Markdown image reference placement accuracy

### 14.4 Link accuracy

A figure link is correct only if:

```text
the figure was extracted
the extracted image corresponds to the correct ground-truth figure
the Markdown contains an image reference
the image reference appears in the correct reading-order position
the caption is associated correctly
```

---

## 15. First Phase Deliverables

Phase 1 should produce a working but minimal generator.

Required deliverables:

```text
Project skeleton
Coordinate utilities
Schema models
Scene graph
Markdown writer
Simple ReportLab renderer
PyMuPDF page rasterizer
Figure cropper
Example generator script
Basic tests
```

The example generator should produce one synthetic document with:

```text
2 pages
1 title
2 headings
several paragraphs
1 simple table
1 raster figure
1 vector figure
2 captions
headers and footers
document.md
document.json
page PNGs
figure PNG crops
```

---

## 16. Success Criteria for Phase 1

Phase 1 is complete when:

1. Running the example script creates a PDF.
2. The generated PDF has visible text, a table, and figures.
3. `truth/document.md` contains the expected Markdown content.
4. `truth/document.json` contains valid structured metadata.
5. Every block has `bbox_pt`, `bbox_px`, and `bbox_norm`.
6. Every figure has a PNG crop.
7. Figure Markdown references point to existing PNG files.
8. Tests pass for coordinate conversion, schema serialization, and Markdown span tracking.
9. The same seed produces deterministic output.

---

## 17. Non-Goals for Phase 1

Do not implement these yet:

```text
advanced document realism
complex pagination
100+ page reports
full table rowspan / colspan rendering
word-level boxes
character-level boxes
COCO export
advanced degradation
scanned document simulation
OCR benchmarking
model training pipeline
```

These can be added after the MVP is stable.
