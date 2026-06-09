# Parser Pipeline Guide

## Purpose

This guide is for users and developers building PDF parsing pipelines against `synthetic_pdf_bench`.

The benchmark gives you:

- a source PDF
- canonical Markdown
- canonical JSON truth
- rendered page images
- ground-truth figure crops

You should treat the scene-graph-generated truth as the reference output.

## Dataset Structure

Each generated document directory looks like this:

```text
synthetic_000001/
  document.pdf
  truth/
    document.json
    document.md
    manifest.json
    pages/
      page_001.png
      page_002.png
    figures/
      fig_001.png
      fig_002.png
```

### File meanings

- `document.pdf`
  The input file for your parsing pipeline.

- `truth/document.md`
  Canonical Markdown for the document.

- `truth/document.json`
  Canonical structured truth, including blocks, tables, figures, bboxes, and metadata.

- `truth/manifest.json`
  Per-document summary including seed, recipe, variant, counts, and quality checks.

- `truth/pages/*.png`
  Rasterized page images from the generated PDF.

- `truth/figures/*.png`
  Ground-truth figure crops derived from the rendered PDF pages.

## How To Use The Dataset

The intended workflow is:

1. Generate one or more documents.
2. Run your parser on each `document.pdf`.
3. Convert your parser outputs into the expected prediction directory shape.
4. Run the evaluator against `truth/` and your prediction directory.

## Expected Parser Output Shape

Your parser output directory should look like this:

```text
prediction/
  document.md
  prediction.json
  figures/
    fig_001.png
```

`document.md` is optional if `prediction.json` already contains the `markdown` field.

### Minimal `prediction.json`

```json
{
  "doc_id": "optional",
  "markdown": "# Predicted Markdown",
  "blocks": [
    {
      "block_id": "b000001",
      "type": "paragraph",
      "page_index": 0,
      "bbox_pt": [72, 100, 540, 130],
      "text": "Optional extracted text",
      "markdown": "Optional block markdown",
      "metadata": {}
    }
  ],
  "tables": [
    {
      "table_id": "tbl_001",
      "matrix": [["A", "B"], ["C", "D"]],
      "page_index": 0,
      "bbox_pt": [72, 100, 540, 180],
      "metadata": {}
    }
  ],
  "figures": [
    {
      "figure_id": "fig_001",
      "page_index": 0,
      "bbox_pt": [72, 200, 540, 360],
      "markdown_ref": "![Figure 1](figures/fig_001.png)",
      "png_path": "figures/fig_001.png",
      "metadata": {}
    }
  ],
  "metadata": {
    "parser_name": "your-parser"
  }
}
```

## Evaluation

### Run the evaluator

```bash
uv run synthetic-pdf-bench evaluate \
  --truth output/synthetic_000001/truth \
  --prediction path/to/parser/output \
  --output output/synthetic_000001/evaluation.json
```

### Current metrics

- Markdown normalized exact match
- Markdown token precision, recall, and F1
- Block bbox mean IoU for matched block ids
- Table matrix exact match rate
- Figure count match
- Figure bbox mean IoU
- Figure Markdown reference match rate

## Dummy Parser For Smoke Testing

Use the built-in dummy parser when you want to verify the evaluator path without using a real parser:

```bash
uv run synthetic-pdf-bench dummy-parse \
  --truth output/synthetic_000001/truth \
  --prediction output/synthetic_000001/dummy_prediction
```

Then evaluate:

```bash
uv run synthetic-pdf-bench evaluate \
  --truth output/synthetic_000001/truth \
  --prediction output/synthetic_000001/dummy_prediction
```

This should produce perfect scores.

## Practical Guidance For Parser Developers

- Start by targeting Markdown quality first.
- Then add block bounding boxes using the same page coordinate convention as truth.
- Then add table matrices and figure references.
- Keep stable ids if your parser can preserve or map them, because block-level IoU currently matches by id.
- If your parser cannot provide block ids, expect partial structural scoring until id-matching logic is expanded.

## Coordinate Convention

Bounding boxes use point units:

```text
bbox_pt = [x0, y0, x1, y1]
origin = bottom-left
unit = points
```

This matches the canonical truth format in `document.json`.
