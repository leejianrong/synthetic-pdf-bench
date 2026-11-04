# synthetic-pdf-bench

Synthetic PDF generator with exact scene-graph ground truth, for training and evaluating Docling-style document models (layout, reading order, tables, PDF-to-Markdown). Truth is exported from the scene graph, never parsed back from the PDF.

## Commands

- Setup: `uv sync`
- Test: `uv run pytest -q`
- Lint: `uv run --with ruff ruff check src tests scripts`
- Generate one doc: `uv run synthetic-pdf-bench --output output/x --seed 1 --recipe data/recipes/canonical/<name>.json`
- Rehearse layout training on CPU (optional stack, see README): `.venv-train/bin/python -m pytest tests/test_train_layout.py`
- Validate a research recipe: `scripts/validate_research_recipe.py`
- Install the pre-push hook (runs lint + tests): `ln -sf ../../scripts/git-hooks/pre-push .git/hooks/pre-push`

## Layout

- `src/synthetic_pdf_bench/`: `schema` (scene graph), `layout`, `render`, `markdown`, `evaluation`, `generators`, `quality.py`
- `data/recipes/canonical/`: generator-ready recipes. `data/recipes/research/`: intermediate research artifacts
- `docs/`: read `implementation-status.md` for status/next steps; `recipe-enrichment-handbook.md` and `canonical-assembly-workflow.md` before touching recipes

## Conventions

- Trust the code over the docs where they disagree, and fix the docs in the same change.
- Branch per change off fresh `main`, land via PR, CI (lint + tests) green first. Don't push to `main`.
- Smallest diff that works: reuse existing code, delete what you supersede, no speculative options. Comments only for a non-obvious why. State net lines (`+N / -M`) in the PR.
- Every bug fix gets a failing test first. Tests must be deterministic (seeded, no timing).
- Update README/docs in the same PR as the behavior they describe.
- Never commit `output/` or secrets. The repo is public (Apache-2.0).
- A canonical recipe is only done when it passes `load_recipe` and a sample PDF generates; tick it in `docs/canonical-recipe-backlog.md` only then.
- RunPod jobs go through `scripts/runpod_launch.sh` (runpod-jobs skill; spend cap `TOTAL_CAP_USD`=5, ledger `output/runpod/spend.jsonl`). The key is read from `~/.runpod/config.toml` (single-quoted `apikey`), never printed. Use `python:3.12` with torch from the PyTorch cu124 index alone; run detached (`setsid nohup`); afterwards `runpodctl pod list` must show no `syn-*` pod (other projects' pods are not ours). Rehearse on CPU first.
