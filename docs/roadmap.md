# Roadmap

## Positioning

A dataset generation tool: produce large, diverse, exactly-labelled document corpora to
train models (layout detection, reading order, table structure) and to test ingestion/RAG
pipelines. Content comes from curated recipes; LLM-filled content is optional and secondary.

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
   - [ ] Still to add: table styles, header/footer text per recipe (the header string is hardcoded to the SEA report), more font families (needs bundled font files)
- [ ] Table cell text is clipped in rendered tables (cell bboxes vs drawn text); investigate and add a fit test
- [ ] Timeline figure labels overlap
   - [ ] Degradation profiles (scan noise, skew, blur, rasterized pages) with transformed truth
   - [ ] Parallel generation; train/val/test splits grouped by recipe and template to avoid leakage
   - [ ] YOLO and HF dataset/parquet exporters; dataset card and versioning
2. **Slides (`.pptx`):** python-pptx generation with exact shape geometry, PDF via LibreOffice, Docker image.
3. **Word and spreadsheets (`.docx`, `.xlsx`):** python-docx/openpyxl, bbox recovery with provenance.
4. **Evaluation and RAG:** benchmark runner over a dataset; retrieval Q&A ground truth derived from the scene graph.
5. **Content breadth:** recipes beyond SEA history (finance, policy, manuals, academic), checking source licensing for training use.
