# Roadmap

## Positioning

A training-data generator: produce large, diverse, exactly-labelled document corpora to
train a Docling-style model (layout detection, reading order, table structure, PDF-to-Markdown).
Benchmarking is the evaluation side: scoring our model and existing parsers (Docling as the
baseline) on the same truth. It also serves ingestion/RAG testing. Content comes from curated recipes; LLM-filled content is optional and secondary.

## Decisions

- **Formats:** PDF (native), `.pptx`, `.docx`, `.xlsx`, each also exported to PDF. Native Office files are kept as deliverables.
- **LibreOffice** is an optional `office` extra, shipped in a Docker image. The fast test layer never needs it.
- **Taxonomy:** DocLayNet's 11 layout classes. Extend only when a generator emits something that does not fit (equation, sidebar, slide-title, spreadsheet-region).
- **First training targets:** layout detection and reading order (both come from the same truth).
- **Page images** are written alongside PDFs.
- **Truth guarantee by format.** Generated PDFs and `.pptx` have exact geometry from the scene graph. For `.docx` and `.xlsx`, LibreOffice decides pagination, so content and reading order are exact but page bboxes are recovered by matching known text in the PDF. Record this as per-block bbox provenance (`source` vs `recovered`) when the first such adapter lands, and drop pages where matching fails.

## Phases

1. **Training-data core (PDF path)**
   - [x] COCO export with DocLayNet classes and per-page reading order (`export-coco`)
   - [x] Template randomization: `--variant random` samples page size, margins, type sizes, font family, columns and page-number position per seed
   - [ ] Header and footer text come from recipe `metadata.header_text` / `footer_text` (default: the title before the colon, and "Synthetic benchmark document"). Still to add: table styles, more font families (needs bundled font files)
- [x] Table cell text clipping fixed: content-sized columns, row heights from wrapped cell lines, lines recorded in `cell.metadata.lines`
- [x] Timeline figure labels overlap (labels take the first free height lane)
   - [x] Degradation profiles (`--degrade light_scan|heavy_scan`): skew, shift, contrast, blur, noise, JPEG; image-only scan PDF; `bbox_px` transformed
   - [ ] Still to add: perspective/page-curl, bleed-through, stamps/handwriting overlays, color-photo profile, rotated (90/180) pages
   - [x] Parallel generation (`--workers`) and train/val/test splits grouped by recipe/template/document (`--splits`, `--split-by`), per-split COCO files
   - [x] YOLO and Hugging Face imagefolder exporters with a dataset card
   - [ ] Parquet export and dataset versioning
2. **Slides (`.pptx`):** python-pptx generation with exact shape geometry, PDF via LibreOffice, Docker image.
3. **Word and spreadsheets (`.docx`, `.xlsx`):** python-docx/openpyxl, bbox recovery with provenance.
4. **Evaluation and RAG:** ~~benchmark runner over a dataset~~ (done: `benchmark`); retrieval Q&A ground truth derived from the scene graph.
5. **Content breadth:** recipes beyond SEA history (finance, policy, manuals, academic), checking source licensing for training use.
