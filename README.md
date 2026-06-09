# synthetic_pdf_bench

`synthetic_pdf_bench` generates synthetic PDFs with deterministic ground truth for PDF-to-Markdown evaluation.

Phase 1 uses a scene-graph-first pipeline:

```text
semantic content -> planned layout boxes -> scene graph -> PDF rendering -> JSON/Markdown export -> page rasterization -> figure crops
```

Ground truth is never recovered by parsing the generated PDF. The scene graph is the canonical source for block text, reading order, coordinates, tables, figures, and Markdown spans.

## Quick start

```bash
uv sync
uv run synthetic-pdf-bench --output output/synthetic_000001 --seed 123 --recipe data/recipes/sea_historical_report_v1.json
```

This writes one document directory:

```text
output/synthetic_000001/
  document.pdf
  truth/
    document.json
    document.md
    manifest.json
    pages/page_001.png
    figures/*.png
```

The default generator loads the canonical Southeast Asia historical recipe from `data/recipes/sea_historical_report_v1.json` and naturally flows it across 3-8 pages. The layout planner creates deterministic boxes for titles, headings, paragraphs, tables, table cells, raster figures, vector figures, captions, repeated headers, footers, and page numbers.

## Dataset generation

Generate a small dataset with deterministic seeds and recipe/layout variants:

```bash
uv run synthetic-pdf-bench \
  --output-root output/small_dataset \
  --count 5 \
  --seed-start 100 \
  --recipe data/recipes/sea_historical_report_v1.json \
  --variants standard compact text_heavy figure_heavy table_heavy
```

Dataset mode writes:

```text
output/small_dataset/
  manifest.json
  synthetic_000001/
  synthetic_000002/
  synthetic_000003/
```

Available variants are `standard`, `compact`, `spacious`, `text_heavy`, `figure_heavy`, `table_heavy`, and `two_column`.

Each document manifest includes a `quality` report. The dataset manifest includes aggregate `summary_stats` for pages, blocks, tables, figures, and variant counts.

## Layout features

The flow layout engine uses ReportLab font metrics for text height estimation and supports:

- one-column and two-column page flow
- repeated headers, footers, and page numbers
- section page-break hints
- paragraphs, lists, tables, figures, captions, footnotes, and references
- split table segments when a table does not fit in the current column/page
- figure captions before or after figures
- page-level validation for bounds and content-block overlap

## Visual benchmark recipe

`data/recipes/visual_benchmark_v1.json` exercises visual extraction with deterministic matplotlib chart figures and richer table shapes.

Supported matplotlib chart kinds:

- `bar_chart`
- `line_chart`
- `stacked_bar`
- `timeline`
- `scatter_plot`
- `heatmap`

Supported table variants:

- narrow table
- wide table
- numeric table
- multilingual table
- wrapped cell text
- merged-cell approximation with span metadata
- multi-page table splitting

## Benchmark evaluation

Expected parser output directory shape:

```text
prediction/
  document.md          # predicted Markdown, optional if prediction.json has markdown
  prediction.json      # structured prediction
  figures/*.png        # optional extracted figure files
```

Minimal `prediction.json` shape:

```json
{
  "doc_id": "optional",
  "markdown": "# Predicted Markdown",
  "blocks": [
    {"block_id": "b000001", "type": "paragraph", "page_index": 0, "bbox_pt": [72, 100, 540, 130]}
  ],
  "tables": [
    {"table_id": "tbl_001", "matrix": [["A", "B"]], "page_index": 0, "bbox_pt": [72, 100, 540, 160]}
  ],
  "figures": [
    {
      "figure_id": "fig_001",
      "page_index": 0,
      "bbox_pt": [72, 200, 540, 360],
      "markdown_ref": "![Figure 1](figures/fig_001.png)",
      "png_path": "figures/fig_001.png"
    }
  ]
}
```

Run the evaluator:

```bash
uv run synthetic-pdf-bench evaluate \
  --truth output/synthetic_000001/truth \
  --prediction path/to/parser/output \
  --output output/synthetic_000001/evaluation.json
```

Metrics include normalized Markdown exact match, Markdown token F1, block bbox IoU, table matrix exact match, figure count match, figure bbox IoU, and figure Markdown reference match.

For smoke testing the evaluator, generate a truth-copy dummy prediction:

```bash
uv run synthetic-pdf-bench dummy-parse \
  --truth output/synthetic_000001/truth \
  --prediction output/synthetic_000001/dummy_prediction
```

## Quality controls

Generation runs quality validation before writing the final manifest. The checks verify:

- all blocks have bounding boxes
- included Markdown blocks have valid spans
- figure caption links resolve
- table cells stay inside table bounding boxes
- content blocks do not overlap
- rendered page images exist and are nonblank
- figure crops exist and are nonblank

## Fonts

The ReportLab renderer automatically uses the built-in `STSong-Light` CID font for text containing Chinese characters. Latin-only text uses Helvetica by default. Future phases can add configurable external fonts such as Noto Sans CJK for higher visual fidelity.
