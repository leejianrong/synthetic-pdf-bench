# Recipe Enrichment Handbook

## Purpose

All future agents working on `data/recipes/` should read this document before editing or creating recipe artifacts.

The goal is to enrich benchmark recipes without breaking determinism, schema quality, or evaluation usefulness.

## Operating Model

Assume the orchestrating chat works in batches of up to five fresh subagents.
Each subagent still owns exactly one topic and exactly one research folder.
Use the `gpt-5.4-mini` model for all recipe enrichment subagents unless a
human explicitly requests a different model.

Rules:

- each subagent run should cover exactly one checklist topic
- each subagent run should work in exactly one research folder
- each batch should include no more than five subagents
- batch topics should use distinct `recipe_id` folders to avoid write conflicts
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
      manifest.json
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

## Token-Efficient Batch Workflow

The orchestrator should process the backlog in batches of up to five topics.

1. Re-read this handbook and `docs/sea-research-topics.md`.
2. Select up to five unchecked topics.
3. Derive predictable `recipe_id` values before delegation:
   - lowercase
   - ASCII
   - underscore-separated
   - remove punctuation and filler words when possible
   - include the country or regional scope and the main historical phrase
   - include date ranges when present
4. Spawn one `gpt-5.4-mini` subagent per selected topic.
5. Send each subagent only the fixed prompt reference plus its topic line and
   `recipe_id`; do not paste long bespoke instructions when the handbook
   already defines the contract.
6. Require each subagent to write a compact `manifest.json` and return a
   short machine-readable handoff.
7. Run the Python validation script over all completed recipe folders in one
   command.
8. Do a short orchestrator sanity check for topic scope and obvious factual
   issues.
9. Update only the checklist items that pass script validation and sanity
   review.

Do not dump full JSON artifacts into the main chat during normal review. Use
the validation script summary, `manifest.json`, and targeted file reads only
when a failure or uncertainty needs inspection.

## Predictable `recipe_id` Examples

- `singapore_colonial_port_governance_1900_1941`
- `singapore_japanese_occupation_1942_1945`
- `malaysia_emergency_security_policy`
- `indonesia_reformasi_decentralization_after_1998`
- `southeast_asia_asean_founding`

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

## Recommended Workflow For Research Artifacts

1. Pick one assigned topic from `docs/sea-research-topics.md`.
2. Draft or update intermediate artifacts under `data/recipes/research/<recipe_id>/`.
3. Keep prose, tables, figures, notes, and manifest data separated while iterating.
4. Validate the research folder with `scripts/validate_research_recipe.py`.
5. Merge into a canonical runtime recipe only after the content is coherent and a human explicitly requests the merge.
6. For canonical merges, generate one or more sample PDFs and review:
   - Markdown output
   - JSON truth
   - figure crops
   - page images
7. Run the test suite if code or canonical recipes changed in a way that affects generation behavior.

## One-Topic Rule

Every subagent run must answer these questions before doing work:

- What exact checklist topic am I covering?
- What exact `recipe_id` folder am I working in?
- Am I creating a new research folder or extending an existing one?

If the answer to the first question is not a single checklist item, narrow the task before proceeding.

## Checklist Update Rule

Subagents must not change topic checkboxes. They should leave the matching
topic unchecked and report whether the artifact set appears complete in their
handoff.

The orchestrating chat changes a checkbox from unchecked to checked only after
the Python validation script passes for that recipe folder and the orchestrator
does a short sanity check confirming the topic scope and any factual uncertainty
are acceptable for review.

Do not check the box if:

- one or more required JSON files are missing
- `manifest.json` is missing or does not match the folder contents
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
- Subagents must not check off topics; checklist updates are owned by the orchestrating chat after review.

## Definition Of Done For Recipe Enrichment

A recipe enrichment task is complete when:

- the assigned topic is covered in a coherent way
- `report_outline.json` exists
- `prose_blocks.json` exists
- `tables.json` exists
- `vector_figures.json` exists
- `manifest.json` exists
- `notes.json` exists
- figure and table content are deterministic
- source notes are present
- the Python validation script passes
- the artifact set is ready for human review

This does not automatically mean the work should be merged into `canonical/`.

## Subagent Prompt Template

Use `gpt-5.4-mini` for all subagents. The orchestrator should keep this prompt
fixed and send only the topic line and `recipe_id` as the variable payload.

```text
You are a recipe enrichment subagent. You are not alone in the codebase; do not
revert edits made by others, and adjust your work to existing changes.

Read:
- docs/recipe-enrichment-handbook.md
- docs/sea-research-topics.md

Task:
Research exactly this one topic and generate recipe enrichment artifacts:
<TOPIC LINE HERE>

Use exactly this recipe_id:
<RECIPE_ID HERE>

Constraints:
- Work on one topic only.
- Use only English, Bahasa Melayu, Bahasa Indonesia, and Simplified Chinese in any PDF-facing text.
- Keep content historically stable, neutral, and benchmark-friendly.
- Put files under: data/recipes/research/<recipe_id>/
- Produce valid JSON only for artifact files.
- Do not modify generator code.
- Do not touch unrelated recipe folders.
- Do not update checkboxes in docs/sea-research-topics.md; the orchestrating chat owns checklist updates after review.

Required outputs:
- report_outline.json
- prose_blocks.json
- tables.json
- vector_figures.json
- manifest.json
- notes.json

Also:
- Leave the matching checkbox in docs/sea-research-topics.md unchanged.
- Keep source URLs in notes.json, not in the chat handoff.
- Return only the compact JSON handoff shape below. Do not include long prose.

Handoff JSON:
{
  "topic": "<TOPIC LINE HERE>",
  "recipe_id": "<RECIPE_ID HERE>",
  "files_changed": [
    "data/recipes/research/<recipe_id>/report_outline.json",
    "data/recipes/research/<recipe_id>/prose_blocks.json",
    "data/recipes/research/<recipe_id>/tables.json",
    "data/recipes/research/<recipe_id>/vector_figures.json",
    "data/recipes/research/<recipe_id>/manifest.json",
    "data/recipes/research/<recipe_id>/notes.json"
  ],
  "artifact_status": "complete_for_review",
  "source_notes_present": true,
  "open_uncertainty": [],
  "checklist_modified": false
}
```

## Required Subagent Handoff

At the end of the run, every subagent should return only a short JSON handoff:

```json
{
  "topic": "One checklist topic only",
  "recipe_id": "stable_recipe_id",
  "files_changed": [
    "data/recipes/research/stable_recipe_id/report_outline.json"
  ],
  "artifact_status": "complete_for_review",
  "source_notes_present": true,
  "open_uncertainty": [],
  "checklist_modified": false
}
```

Keep URLs and detailed source metadata in `notes.json`. The handoff should say
only whether source notes are present unless there is uncertainty the
orchestrator needs to see.

## Review Checklist For The Orchestrator

The orchestrating chat should verify:

- the subagent stayed on one topic
- files were written under the correct `data/recipes/research/<recipe_id>/` folder
- the Python validation script passes for the recipe folder
- `manifest.json` matches the topic, `recipe_id`, files, and content counts
- source notes exist
- unsupported languages were not introduced into PDF-facing text
- open uncertainty in `notes.json` does not block review
- the checklist is updated only after script validation plus orchestrator sanity check

## Python Validation Script

Use `scripts/validate_research_recipe.py` to validate one or more research
recipe folders without manual `jq` inspection or dumping full artifact JSON
into the main chat.

Example usage:

```bash
uv run python scripts/validate_research_recipe.py \
  data/recipes/research/singapore_colonial_port_governance_1900_1941 \
  data/recipes/research/singapore_japanese_occupation_1942_1945
```

Command behavior:

- accept one or more `data/recipes/research/<recipe_id>/` paths
- print one compact result line per recipe folder
- print only failures and warnings with enough detail to fix them
- exit `0` when all folders pass required checks
- exit non-zero when any folder fails required checks
- avoid printing full artifact JSON

Example compact output:

```text
PASS singapore_colonial_port_governance_1900_1941 files=6 sections=5 prose_blocks=20 tables=5 figures=5 warnings=1
WARN singapore_colonial_port_governance_1900_1941 notes.open_questions count=3
FAIL singapore_japanese_occupation_1942_1945 prose_blocks.json missing language at sections[2].blocks[1]
```

The script checks required files, JSON parseability, manifest consistency,
section/table/figure consistency, allowed prose language codes, table
rectangularity, duplicate IDs, source metadata, and obvious unsupported scripts
in PDF-facing strings.

The orchestrator should treat `FAIL` lines as blockers. `WARN` lines are not
automatic blockers, but the orchestrator should inspect any warning that could
affect factual confidence, rendering, or benchmark usefulness before updating a
checkbox. Manual file reads should be reserved for failures, material warnings,
or the final short sanity check.

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

### `manifest.json`

```json
{
  "recipe_id": "example_recipe_id",
  "topic": "One checklist topic only",
  "status": "complete_for_review",
  "files": [
    "report_outline.json",
    "prose_blocks.json",
    "tables.json",
    "vector_figures.json",
    "manifest.json",
    "notes.json"
  ],
  "counts": {
    "outline_sections": 1,
    "prose_blocks": 1,
    "tables": 1,
    "figures": 1
  },
  "source_notes_present": true,
  "open_uncertainty_count": 0,
  "checklist_modified": false
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
  ],
  "source_notes": [
    {
      "source_id": "src_example",
      "title": "Stable source title",
      "publisher": "Source publisher",
      "url": "https://example.org/source",
      "used_for": [
        "Short note on what this source supports."
      ]
    }
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
