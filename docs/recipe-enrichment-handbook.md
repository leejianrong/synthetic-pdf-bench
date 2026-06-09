# Recipe Enrichment Handbook

## Purpose

All future agents working on `data/recipes/` should read this document before editing or creating recipe artifacts.

The goal is to enrich benchmark recipes without breaking determinism, schema quality, or evaluation usefulness.

## Repository Structure For Recipes

Use this structure:

```text
data/recipes/
  canonical/
    <runtime recipe>.json
  research/
    <recipe_id>/
      report_outline.json
      prose_blocks.json
      tables.json
      vector_figures.json
      notes.json
```

Rules:

- `canonical/` contains runtime-ready recipe files consumed by the generator.
- `research/` contains intermediate artifacts used to assemble or revise canonical recipes.
- Do not place temporary experimental files at the top level of `data/recipes/`.

## Language Rules For PDF Content

Only the following languages should appear in the generated PDF text:

- English
- Bahasa Melayu
- Bahasa Indonesia
- Simplified Chinese Mandarin

Broader Southeast Asia may be the research scope, but PDF text must stay within those language constraints.

## Topic Scope

Agents should research the broader Southeast Asia region from 1900 to 2026, not only Singapore, Malaysia, and Indonesia.

Equal attention should be given to:

- Singapore
- Malaysia
- Indonesia
- Thailand
- Vietnam
- Philippines
- Myanmar
- Cambodia
- Laos
- Brunei
- Timor-Leste

## Content Standards

- Prefer historically stable topics, events, institutions, and themes.
- Keep prose neutral and synthetic-benchmark-friendly.
- Avoid speculative claims or unstable current statistics unless clearly versioned and intentionally rounded.
- Treat source metadata as required even if citations are not rendered in the PDF yet.
- Preserve multilingual terms only when they help benchmark extraction.

## Recipe Construction Rules

Canonical recipes should:

- validate against the recipe schema
- include stable `doc_id`
- include `language_profile`
- include `metadata.source_notes`
- organize content into sections with meaningful headings
- use supported block types only
- keep tables rectangular even when approximating merged cells
- keep figure specs deterministic

## Figure Rules

- Prefer vector figures when diagrammatic structure matters.
- Use raster figures when chart appearance matters and the matplotlib backend is appropriate.
- Include enough structured `data` in the figure recipe for regeneration.
- Do not use remote image URLs as runtime dependencies.

## Table Rules

- Use canonical matrices as the truth source.
- If approximating merged cells, keep the matrix rectangular and attach span metadata.
- Use multilingual cells deliberately, not decoratively.
- Make long tables deterministic so split-table evaluation stays stable.

## Recommended Workflow For Agents

1. Pick one topic from `docs/sea-research-topics.md`.
2. Draft or update intermediate artifacts under `data/recipes/research/<recipe_id>/`.
3. Keep prose, tables, and figures separated while iterating.
4. Merge into a canonical runtime recipe only after the content is coherent.
5. Generate one or more sample PDFs and review:
   - Markdown output
   - JSON truth
   - figure crops
   - page images
6. Run the test suite if code or canonical recipes changed in a way that affects generation behavior.

## What Agents Should Not Do

- Do not insert unsupported languages into PDF text.
- Do not add unstable factual claims without metadata notes.
- Do not mix intermediate files into `canonical/`.
- Do not replace structured figure data with opaque blobs if a structured representation is possible.
- Do not introduce ad hoc schema changes without updating the models and tests.

## Definition Of Done For Recipe Enrichment

A recipe enrichment task is complete when:

- the canonical recipe validates and generates successfully
- the output passes quality validation
- figure and table content are deterministic
- source notes are present
- the recipe contributes meaningful benchmark diversity
