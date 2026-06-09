# Canonical Recipe Assembly Workflow

Use this guide when turning validated research artifacts in
`data/recipes/research/` into generator-ready `DocumentRecipe` JSON files under
`data/recipes/canonical/`.

Canonical assembly is a separate workflow from research enrichment. Research
folders preserve source notes, intermediate structure, prose, table matrices,
and figure specs. Canonical recipes are runtime inputs consumed by
`synthetic-pdf-bench`.

## Inputs And Outputs

Input folders:

```text
data/recipes/research/<recipe_id>/
  report_outline.json
  prose_blocks.json
  tables.json
  vector_figures.json
  manifest.json
  notes.json
```

Output file:

```text
data/recipes/canonical/<canonical_doc_id>.json
```

The output must validate as a `DocumentRecipe` from
`src/synthetic_pdf_bench/generators/recipes.py`.

## Agentic Operating Model

Use one subagent per canonical recipe target. Multiple subagents may run in
parallel only when their canonical output files are distinct.

Rules:

- each subagent owns exactly one canonical JSON output
- each subagent may read multiple research folders
- each subagent writes only its assigned `data/recipes/canonical/<doc_id>.json`
- subagents must not edit research folders unless explicitly asked to repair a validation failure
- subagents must not edit generator code
- subagents must not update checklist files unless the orchestrator asks for that exact task
- the orchestrator validates the canonical JSON and generates a sample PDF before marking the canonical backlog item complete

Use `gpt-5.4-mini` for canonical assembly subagents unless a human requests a
different model.

## Required Preflight

Before assembling a canonical recipe, the orchestrator or subagent should run:

```bash
uv run python scripts/validate_research_recipe.py \
  data/recipes/research/<recipe_id_1> \
  data/recipes/research/<recipe_id_2>
```

Do not assemble from research folders that fail validation. Warnings are allowed
only if the orchestrator decides they are non-blocking future-detail questions.

## Canonical Recipe Shape

The output JSON must follow this top-level shape:

```json
{
  "doc_id": "stable_doc_id",
  "title": "Human Readable Title",
  "language_profile": {
    "primary": "en",
    "secondary": ["zh", "ms", "id"],
    "encoding": "UTF-8"
  },
  "metadata": {
    "document_family": "synthetic_historical_research_report",
    "source_notes": []
  },
  "sections": []
}
```

Supported block types are:

- `paragraph`
- `table`
- `figure`
- `list`
- `footnote`
- `reference`

## Assembly Rules

For each selected research folder:

1. Read `manifest.json` and confirm the expected topic and `recipe_id`.
2. Read `prose_blocks.json`.
3. Read `tables.json`.
4. Read `vector_figures.json`.
5. Read `notes.json`.
6. Create one or more canonical sections.
7. Pull paragraph blocks from `prose_blocks.json`.
8. Insert matching tables and figures into the section whose heading matches `suggested_section`.
9. Preserve source notes in both block metadata and document metadata.

Recommended block order inside each canonical section:

```text
paragraphs
first matching table
first matching figure
remaining paragraphs, tables, and figures as needed
```

Keep each canonical recipe focused enough to generate a readable PDF. If a
single country has many research topics, prefer several canonical recipes over
one oversized recipe.

## Source Notes Preservation

Canonical recipes must preserve source metadata:

- copy research `notes.source_notes` or `notes.research_basis` entries into `metadata.source_notes`
- add each research folder's `recipe_id` and topic to `metadata.source_notes`
- copy section-level `source_notes` into `section.metadata.source_notes`
- copy prose block metadata where present
- add table and figure source notes to each block's `metadata.source_notes`

If source notes are long, preserve them in structured metadata rather than
rendering them as PDF-facing prose.

## Table Conversion

Research table:

```json
{
  "table_id": "tbl_example",
  "title": "Example Table",
  "matrix": [["A", "B"], ["1", "2"]],
  "notes": ["Source note."],
  "suggested_section": "Section Heading"
}
```

Canonical table block:

```json
{
  "type": "table",
  "table_id": "tbl_example",
  "title": "Example Table",
  "caption": "Example Table",
  "matrix": [["A", "B"], ["1", "2"]],
  "metadata": {
    "source_notes": ["Source note."],
    "source_research_recipe": "example_recipe_id"
  }
}
```

Tables must stay rectangular and include at least one header row and one body
row.

## Figure Conversion

Research figure:

```json
{
  "figure_id": "fig_example",
  "kind": "timeline",
  "title": "Example Figure",
  "caption": "Short caption.",
  "data": {},
  "suggested_section": "Section Heading"
}
```

Canonical figure block:

```json
{
  "type": "figure",
  "figure_id": "fig_example",
  "kind": "timeline",
  "source_type": "vector",
  "title": "Example Figure",
  "caption": "Short caption.",
  "data": {},
  "metadata": {
    "source_research_recipe": "example_recipe_id"
  }
}
```

Use `source_type: "vector"` for research `vector_figures.json` entries.

## Validation And PDF Smoke Test

After writing a canonical recipe, run:

```bash
uv run python -c "from pathlib import Path; from synthetic_pdf_bench.generators.recipes import load_recipe; load_recipe(Path('data/recipes/canonical/<canonical_doc_id>.json'))"
```

Then generate a sample PDF:

```bash
uv run synthetic-pdf-bench \
  --output output/<canonical_doc_id>_smoke \
  --seed 123 \
  --recipe data/recipes/canonical/<canonical_doc_id>.json
```

If the generator succeeds, inspect the output manifest and confirm the PDF,
Markdown, JSON truth, page images, and figure crops were created.

## Fixed Subagent Prompt Template

Use this prompt when delegating one canonical JSON to a subagent:

```text
Read:
- docs/canonical-assembly-workflow.md
- docs/canonical-recipe-backlog.md
- docs/recipe-enrichment-handbook.md

Task:
Assemble exactly this canonical DocumentRecipe:
<CANONICAL BACKLOG LINE>

Use exactly this output path:
data/recipes/canonical/<canonical_doc_id>.json

Use these research folders only:
<RESEARCH FOLDER LIST>

Constraints:
- Write only the assigned canonical JSON file.
- Do not modify research folders.
- Do not modify generator code.
- Do not update checklist files.
- Preserve source notes in metadata.
- Use only generator-supported block types.
- Produce valid JSON.

Validation:
- Load the canonical recipe with synthetic_pdf_bench.generators.recipes.load_recipe.
- Generate one sample PDF with synthetic-pdf-bench.
- Return a compact JSON handoff with files changed, validation command results, generated output path, and open issues.
```

## Orchestrator Review

The orchestrator should verify:

- the subagent used only the assigned research folders
- the canonical recipe validates with `load_recipe`
- sample PDF generation succeeds
- source notes are present in `metadata.source_notes`
- tables and figures from research artifacts appear in the canonical sections
- no research folders, generator code, or unrelated canonical recipes were changed

