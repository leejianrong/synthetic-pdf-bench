# Recipe Enrichment Handbook

## Purpose

All future agents working on `data/recipes/` should read this document before editing or creating recipe artifacts.

The goal is to enrich benchmark recipes without breaking determinism, schema quality, or evaluation usefulness.

## Operating Model

Assume one fresh subagent is spun up for one topic at a time.

Rules:

- each subagent run should cover exactly one checklist topic
- each subagent run should work in exactly one research folder
- the subagent should not try to clear multiple checklist items in one pass
- the subagent should not merge into `canonical/` unless explicitly instructed

This keeps review, rollback, and factual verification manageable.

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

## Required Reading For Every Subagent

Before making any edits, every subagent should read:

- `docs/recipe-enrichment-handbook.md`
- `docs/sea-research-topics.md`

Recommended reference reads when needed:

- `docs/implementation-status.md`
- `docs/parser-pipeline-guide.md`
- an existing research folder under `data/recipes/research/`

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

## One-Topic Rule

Every subagent run must answer these questions before doing work:

- What exact checklist topic am I covering?
- What exact `recipe_id` folder am I working in?
- Am I creating a new research folder or extending an existing one?

If the answer to the first question is not a single checklist item, narrow the task before proceeding.

## Checklist Update Rule

Change a checkbox from unchecked to checked only when all required artifact files for that topic are complete enough for review.

Do not check the box if:

- one or more required JSON files are missing
- the artifact set is still exploratory
- major factual uncertainty remains unresolved
- the topic was only partially covered

If work started but is incomplete, leave the checkbox unchecked and record the state in `notes.json`.

## What Agents Should Not Do

- Do not insert unsupported languages into PDF text.
- Do not add unstable factual claims without metadata notes.
- Do not mix intermediate files into `canonical/`.
- Do not replace structured figure data with opaque blobs if a structured representation is possible.
- Do not introduce ad hoc schema changes without updating the models and tests.
- Do not silently broaden the assignment from one topic to multiple topics.
- Do not check off a topic just because a folder was created.

## Definition Of Done For Recipe Enrichment

A recipe enrichment task is complete when:

- the assigned topic is covered in a coherent way
- `report_outline.json` exists
- `prose_blocks.json` exists
- `tables.json` exists
- `vector_figures.json` exists
- `notes.json` exists if there are open questions or non-obvious decisions
- figure and table content are deterministic
- source notes are present
- the artifact set is ready for human review

This does not automatically mean the work should be merged into `canonical/`.

## Required Subagent Handoff

At the end of the run, every subagent should provide a short structured handoff covering:

- exact topic covered
- `recipe_id`
- files created or updated
- whether the checklist was updated
- open factual uncertainty
- any recommended follow-up work

Recommended handoff shape:

```text
Topic:
recipe_id:
Files changed:
Checklist updated:
Open questions:
Follow-up:
```

## Review Checklist For The Orchestrator

The orchestrating chat should verify:

- the subagent stayed on one topic
- files were written under the correct `data/recipes/research/<recipe_id>/` folder
- JSON files are present and valid
- source notes exist
- unsupported languages were not introduced into PDF-facing text
- the checklist was updated only when appropriate

## Appendix: Minimal File Templates

Use these as the minimum expected shapes for intermediate research artifacts.

### `report_outline.json`

```json
{
  "title": "Topic Title",
  "abstract": "Short synthetic benchmark abstract.",
  "sections": [
    {
      "heading": "Section Heading",
      "bullet_points": [
        "Stable historical point one.",
        "Stable historical point two."
      ],
      "suggested_tables": [
        {
          "table_id": "tbl_example",
          "title": "Example Table",
          "description": "What the table should compare."
        }
      ],
      "suggested_figures": [
        {
          "figure_id": "fig_example",
          "kind": "timeline",
          "title": "Example Figure",
          "description": "What the figure should show."
        }
      ],
      "source_notes": [
        "High-level source note."
      ]
    }
  ]
}
```

### `prose_blocks.json`

```json
{
  "title": "Topic Title",
  "sections": [
    {
      "heading": "Section Heading",
      "blocks": [
        {
          "type": "paragraph",
          "text": "Neutral synthetic benchmark prose.",
          "language": "en",
          "metadata": {
            "source_notes": [
              "Short source note."
            ]
          }
        }
      ],
      "source_notes": [
        "Optional section-level source note."
      ]
    }
  ]
}
```

### `tables.json`

```json
{
  "tables": [
    {
      "table_id": "tbl_example",
      "title": "Example Table",
      "matrix": [
        ["Column A", "Column B"],
        ["Value 1", "Value 2"]
      ],
      "notes": [
        "Keep rows deterministic."
      ],
      "suggested_section": "Section Heading"
    }
  ]
}
```

### `vector_figures.json`

```json
{
  "figures": [
    {
      "figure_id": "fig_example",
      "kind": "timeline",
      "title": "Example Figure",
      "caption": "Short deterministic caption.",
      "data": {
        "orientation": "horizontal",
        "events": [
          {"year": 1945, "label": "Event"}
        ]
      },
      "suggested_section": "Section Heading"
    }
  ]
}
```

### `notes.json`

```json
{
  "recipe_id": "example_recipe_id",
  "topic": "One checklist topic only",
  "open_questions": [
    "Any factual uncertainty that still needs review."
  ],
  "decisions": [
    "Why a term, table shape, or figure design was chosen."
  ]
}
```

## Appendix: Naming Conventions

- `recipe_id`: short, stable, lowercase, underscore-separated
- `table_id`: `tbl_<topic>_<suffix>`
- `figure_id`: `fig_<topic>_<suffix>`
- one research folder should focus on one coherent topic or tightly related cluster

## Appendix: Suggested `recipe_id` Pattern

Use stable names such as:

- `thailand_1932_revolution`
- `vietnam_doi_moi`
- `philippines_martial_law`
- `asean_founding`

Avoid vague names such as:

- `history_notes`
- `sea_topic_1`
- `draft_recipe`

## Appendix: Merge Guidance

Merge research artifacts into `data/recipes/canonical/` only when:

- prose, tables, and figures are internally consistent
- source notes are present
- generated PDF output passes quality validation
- the new canonical recipe adds benchmark diversity rather than duplicating an existing recipe with only cosmetic changes
