# synthetic-pdf-bench

Generates synthetic documents with exact scene-graph ground truth, to train layout/reading-order models and to test PDF ingestion pipelines. Planned: `.pptx`, `.docx`, `.xlsx` (LibreOffice as an optional extra). Plan: `docs/roadmap.md`. What exists: `docs/implementation-status.md`.

## Commands

- Setup / test / lint: `uv sync`, `uv run pytest -q`, `uv run --with ruff ruff check src tests scripts`
- Pre-push hook (lint + tests, mirrors CI): `ln -sf ../../scripts/git-hooks/pre-push .git/hooks/pre-push`
- One doc: `uv run synthetic-pdf-bench --output output/x --seed 1 --recipe data/recipes/canonical/<name>.json`
- Dataset: `--output-root DIR --count N --workers W --splits train=.8 val=.1 test=.1 --split-by recipe`, then `export-coco DIR`
- Scan: `--degrade light_scan|heavy_scan`. Variants include `random` (sampled page template).
- Regenerate the README image after changing the look: `uv run python scripts/readme_figure.py`

## Invariants (not visible from any one file)

- Truth comes from the scene graph, never from parsing the PDF.
- The planner decides, the renderer obeys. The renderer draws only what the planner recorded in block metadata (`font_size`, `line_height`, `font_family`; table `cell_padding` and per-cell `lines`). Never re-measure or re-wrap in the renderer: that drift caused both the text-overflow and the clipped-table bugs.
- Three coordinate systems: `bbox_pt` and `bbox_norm` describe the digital PDF (y-up); `bbox_px` describes the page image (y-down) and follows degradation. COCO export uses `bbox_px`.
- Layout/render changes: passing tests were not enough twice. Run `tests/test_text_fits_bbox.py` and `tests/test_table_cells_fit.py` (they check the rendered PDF) and look at rendered pages.
- A new test guards nothing until you have watched it fail: break the code temporarily, confirm red, restore.

## Workflow

- Trust the code over the docs where they disagree, and fix the docs in the same change.
- Branch per change off fresh `main`, PR, CI (lint + tests) green before merge. Never push to `main`.
- Smallest diff that works: reuse existing code, delete what you supersede, no speculative options, comments only for a non-obvious why. State net lines (`+N / -M`) in the PR.
- Bug fix: failing test first. Tests are seeded and deterministic.
- README stays short (value, quick start, 3 usages); detail goes in `docs/reference.md`. Update README/docs in the PR that changes the behavior.
- A canonical recipe is done only when it passes `load_recipe` and a sample PDF generates; tick it in `docs/canonical-recipe-backlog.md` then. Read `docs/recipe-enrichment-handbook.md` and `docs/canonical-assembly-workflow.md` before touching recipes.
- Never commit `output/` or secrets. The repo is public (Apache-2.0).
