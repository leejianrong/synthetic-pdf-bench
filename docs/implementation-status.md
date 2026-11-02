# Implementation Status

What exists today. The plan is in [roadmap.md](roadmap.md). Where this file and the code disagree, trust the code and fix this file.

`synthetic-pdf-bench` generates synthetic documents with exact ground truth, to train layout and reading-order models and to test PDF ingestion pipelines. Truth is exported from the scene graph, never recovered by parsing the PDF.

## Implemented

### Generation pipeline

- Recipe-driven, seeded generation: recipe + variant + seed gives the same document
- Scene graph with page and block truth, ReportLab PDF rendering, PyMuPDF page rasterization, figure crops, Markdown and JSON truth
- The planner decides every size and line (font size, line height, font family, table cell lines); the renderer draws exactly what it recorded. Tests check on the rendered PDF that text and table cells sit inside their boxes.

### Layout and templates

- One- and two-column flow; repeated headers, footers, page numbers; section page-break hints
- Paragraphs, lists, tables, figures, captions, footnotes, references
- Tables: content-sized columns, row heights from wrapped cell text, splitting across columns and pages, word breaking in cells narrower than a word
- Variants: `standard`, `compact`, `spacious`, `text_heavy`, `figure_heavy`, `table_heavy`, `two_column`, `random`. `random` samples page size (Letter/A4), margins, type sizes, font family (Helvetica/Times/Courier), columns and page-number position per seed, and stores it in `metadata.layout_style`.
- Quality validation per document (bounds, overlap, spans, caption links, image checks)

### Figures

- ReportLab vector figures; matplotlib raster charts (bar, line, stacked bar, timeline, scatter, heatmap)

### Datasets, exports, degradation

- Dataset mode with manifest and summary stats; `--workers N` parallel generation (output identical for any N)
- Leakage-safe `--splits` grouped by recipe, template or document, with `splits.json`
- `export-coco`: DocLayNet-style classes, per-page `reading_order`, one file per split
- `--degrade light_scan|heavy_scan`: skew, shift, contrast, blur, noise, JPEG; image-only scan PDF plus `document_clean.pdf`; `bbox_px` transformed

### Evaluation

- Evaluator (Markdown match and F1, block/figure IoU, table matrix match) and a dummy parser for smoke tests

### Content

- Canonical recipes in `data/recipes/canonical/`: SEA historical report, visual benchmark, Singapore history, Malaysia history, Malaya/Malaysia state formation, Singapore-Malaysia 1963-65, Indonesia colonial and nationalist origins
- Research and enrichment artifacts (one folder per topic) in `data/recipes/research/`; workflow in `recipe-enrichment-handbook.md` and `canonical-assembly-workflow.md`

## Known limitations

- Only PDF output; no `.pptx`, `.docx` or `.xlsx` yet
- All recipes are SEA-history reports; the page header text is hardcoded to that report
- Timeline figure labels overlap
- Two splits cannot be balanced well with few recipes (groups are not split)
- Degradation covers skew, shift, contrast, blur, noise and JPEG only (no perspective, curl, bleed-through, stamps, rotated pages)
- Boxes on degraded pages are axis-aligned around the skewed content, so they are looser than the text
- No benchmark runner over a whole dataset and no dataset-level parser report
- No dedicated recipe validation CLI (`scripts/validate_research_recipe.py` checks research folders only)
