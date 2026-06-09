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

This writes:

```text
document.pdf
truth/document.json
truth/document.md
truth/pages/page_001.png
truth/figures/fig_001.png
```

The default generator loads the canonical Southeast Asia historical recipe from `data/recipes/sea_historical_report_v1.json` and naturally flows it across 3-8 pages. The layout planner creates deterministic boxes for titles, headings, paragraphs, tables, table cells, raster figures, vector figures, captions, repeated headers, footers, and page numbers.

## Fonts

The ReportLab renderer automatically uses the built-in `STSong-Light` CID font for text containing Chinese characters. Latin-only text uses Helvetica by default. Future phases can add configurable external fonts such as Noto Sans CJK for higher visual fidelity.
