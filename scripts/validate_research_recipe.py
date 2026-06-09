#!/usr/bin/env python3
"""Validate recipe research artifact folders.

The output is intentionally compact so orchestrator chats can validate batches
without reading full JSON artifacts into context.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "report_outline.json",
    "prose_blocks.json",
    "tables.json",
    "vector_figures.json",
    "manifest.json",
    "notes.json",
}

ALLOWED_LANGUAGES = {"en", "ms", "id", "zh-Hans"}

UNSUPPORTED_SCRIPT_RE = re.compile(
    "["
    "\u0900-\u097f"  # Devanagari
    "\u0e00-\u0e7f"  # Thai
    "\u0e80-\u0eff"  # Lao
    "\u1000-\u109f"  # Myanmar
    "\u1780-\u17ff"  # Khmer
    "\u3040-\u309f"  # Hiragana
    "\u30a0-\u30ff"  # Katakana
    "\uac00-\ud7af"  # Hangul
    "]"
)


@dataclass
class ValidationResult:
    recipe_id: str
    files: int = 0
    sections: int = 0
    prose_blocks: int = 0
    tables: int = 0
    figures: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate one or more data/recipes/research/<recipe_id> folders."
    )
    parser.add_argument("folders", nargs="+", type=Path)
    args = parser.parse_args()

    results = [validate_folder(folder) for folder in args.folders]
    for result in results:
        print_result(result)
    return 1 if any(not result.ok for result in results) else 0


def validate_folder(folder: Path) -> ValidationResult:
    result = ValidationResult(recipe_id=folder.name)

    if not folder.exists():
        result.errors.append(f"folder does not exist: {folder}")
        return result
    if not folder.is_dir():
        result.errors.append(f"path is not a directory: {folder}")
        return result

    present_files = {path.name for path in folder.iterdir() if path.is_file()}
    result.files = len(present_files & REQUIRED_FILES)

    missing = sorted(REQUIRED_FILES - present_files)
    for filename in missing:
        result.errors.append(f"missing required file {filename}")

    unrelated_json = sorted(
        name for name in present_files if name.endswith(".json") and name not in REQUIRED_FILES
    )
    for filename in unrelated_json:
        result.errors.append(f"unexpected json file {filename}")

    data: dict[str, Any] = {}
    for filename in sorted(REQUIRED_FILES & present_files):
        try:
            data[filename] = load_json(folder / filename)
        except ValueError as exc:
            result.errors.append(f"{filename} {exc}")

    if result.errors:
        return result

    outline = data["report_outline.json"]
    prose = data["prose_blocks.json"]
    tables_doc = data["tables.json"]
    figures_doc = data["vector_figures.json"]
    manifest = data["manifest.json"]
    notes = data["notes.json"]

    validate_manifest(result, folder, manifest, notes, outline, prose, tables_doc, figures_doc)
    validate_outline(result, outline)
    validate_prose(result, prose)
    validate_tables(result, tables_doc, outline)
    validate_figures(result, figures_doc, outline)
    validate_notes(result, notes)
    validate_pdf_facing_scripts(result, outline, prose, tables_doc, figures_doc)

    return result


def load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno} column {exc.colno}") from exc


def validate_manifest(
    result: ValidationResult,
    folder: Path,
    manifest: Any,
    notes: Any,
    outline: Any,
    prose: Any,
    tables_doc: Any,
    figures_doc: Any,
) -> None:
    if not isinstance(manifest, dict):
        result.errors.append("manifest.json root must be an object")
        return

    recipe_id = manifest.get("recipe_id")
    if recipe_id != folder.name:
        result.errors.append(
            f"manifest.recipe_id expected {folder.name!r}, got {recipe_id!r}"
        )
    if isinstance(notes, dict) and manifest.get("topic") != notes.get("topic"):
        result.errors.append("manifest.topic does not match notes.topic")

    manifest_files = manifest.get("files")
    if sorted(manifest_files or []) != sorted(REQUIRED_FILES):
        result.errors.append("manifest.files must list exactly the required files")

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        result.errors.append("manifest.counts must be an object")
    else:
        expected_counts = observed_counts(outline, prose, tables_doc, figures_doc)
        for key, expected in expected_counts.items():
            observed = counts.get(key)
            if observed != expected:
                result.errors.append(
                    f"manifest.counts.{key} expected {expected}, got {observed!r}"
                )

    if manifest.get("checklist_modified") is not False:
        result.errors.append("manifest.checklist_modified must be false")

    status = manifest.get("status")
    if status not in {"complete_for_review", "incomplete"}:
        result.warnings.append(f"manifest.status unusual value {status!r}")

    result.sections = observed_counts(outline, prose, tables_doc, figures_doc)[
        "outline_sections"
    ]
    result.prose_blocks = observed_counts(outline, prose, tables_doc, figures_doc)[
        "prose_blocks"
    ]
    result.tables = observed_counts(outline, prose, tables_doc, figures_doc)["tables"]
    result.figures = observed_counts(outline, prose, tables_doc, figures_doc)["figures"]


def observed_counts(
    outline: Any, prose: Any, tables_doc: Any, figures_doc: Any
) -> dict[str, int]:
    outline_sections = as_list(outline.get("sections")) if isinstance(outline, dict) else []
    prose_sections = as_list(prose.get("sections")) if isinstance(prose, dict) else []
    return {
        "outline_sections": len(outline_sections),
        "prose_blocks": sum(len(as_list(section.get("blocks"))) for section in prose_sections),
        "tables": len(as_list(tables_doc.get("tables"))) if isinstance(tables_doc, dict) else 0,
        "figures": len(as_list(figures_doc.get("figures"))) if isinstance(figures_doc, dict) else 0,
    }


def validate_outline(result: ValidationResult, outline: Any) -> None:
    if not isinstance(outline, dict):
        result.errors.append("report_outline.json root must be an object")
        return
    require_non_empty_string(result, outline, "title", "report_outline.json")
    require_non_empty_string(result, outline, "abstract", "report_outline.json")
    sections = as_list(outline.get("sections"))
    if not sections:
        result.errors.append("report_outline.json sections must be a non-empty array")
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            result.errors.append(f"report_outline.json sections[{idx}] must be an object")
            continue
        require_non_empty_string(result, section, "heading", f"sections[{idx}]")
        source_notes = as_list(section.get("source_notes"))
        if not source_notes:
            result.errors.append(f"sections[{idx}].source_notes must be non-empty")
        elif len(source_notes) < 2:
            result.warnings.append(f"sections[{idx}].source_notes sparse count={len(source_notes)}")


def validate_prose(result: ValidationResult, prose: Any) -> None:
    if not isinstance(prose, dict):
        result.errors.append("prose_blocks.json root must be an object")
        return
    sections = as_list(prose.get("sections"))
    for section_idx, section in enumerate(sections):
        if not isinstance(section, dict):
            result.errors.append(f"prose sections[{section_idx}] must be an object")
            continue
        for block_idx, block in enumerate(as_list(section.get("blocks"))):
            path = f"prose_blocks.json sections[{section_idx}].blocks[{block_idx}]"
            if not isinstance(block, dict):
                result.errors.append(f"{path} must be an object")
                continue
            language = block.get("language")
            if language not in ALLOWED_LANGUAGES:
                result.errors.append(f"{path} unsupported language {language!r}")
            text = block.get("text")
            if not isinstance(text, str) or not text.strip():
                result.errors.append(f"{path}.text must be a non-empty string")


def validate_tables(result: ValidationResult, tables_doc: Any, outline: Any) -> None:
    if not isinstance(tables_doc, dict):
        result.errors.append("tables.json root must be an object")
        return
    valid_sections = outline_headings(outline)
    seen_ids: set[str] = set()
    for table_idx, table in enumerate(as_list(tables_doc.get("tables"))):
        path = f"tables.json tables[{table_idx}]"
        if not isinstance(table, dict):
            result.errors.append(f"{path} must be an object")
            continue
        table_id = table.get("table_id")
        check_unique_id(result, seen_ids, table_id, path, "table_id")
        section = table.get("suggested_section")
        if section not in valid_sections:
            result.errors.append(f"{path}.suggested_section does not match outline heading")
        matrix = table.get("matrix")
        if not isinstance(matrix, list) or not matrix:
            result.errors.append(f"{path}.matrix must be a non-empty array")
            continue
        widths = []
        for row_idx, row in enumerate(matrix):
            if not isinstance(row, list) or not row:
                result.errors.append(f"{path}.matrix[{row_idx}] must be a non-empty array")
                continue
            widths.append(len(row))
            for col_idx, cell in enumerate(row):
                if not isinstance(cell, str):
                    result.errors.append(
                        f"{path}.matrix[{row_idx}][{col_idx}] must be a string"
                    )
                elif len(cell) > 300:
                    result.warnings.append(
                        f"{path}.matrix[{row_idx}][{col_idx}] long cell length={len(cell)}"
                    )
        if len(set(widths)) > 1:
            result.errors.append(f"{path}.matrix is not rectangular widths={sorted(set(widths))}")
        if len(matrix) > 50:
            result.warnings.append(f"{path}.matrix many rows count={len(matrix)}")


def validate_figures(result: ValidationResult, figures_doc: Any, outline: Any) -> None:
    if not isinstance(figures_doc, dict):
        result.errors.append("vector_figures.json root must be an object")
        return
    valid_sections = outline_headings(outline)
    seen_ids: set[str] = set()
    for figure_idx, figure in enumerate(as_list(figures_doc.get("figures"))):
        path = f"vector_figures.json figures[{figure_idx}]"
        if not isinstance(figure, dict):
            result.errors.append(f"{path} must be an object")
            continue
        figure_id = figure.get("figure_id")
        check_unique_id(result, seen_ids, figure_id, path, "figure_id")
        section = figure.get("suggested_section")
        if section not in valid_sections:
            result.errors.append(f"{path}.suggested_section does not match outline heading")
        data = figure.get("data")
        if not isinstance(data, dict):
            result.errors.append(f"{path}.data must be an object")
        elif "render_hints" not in data:
            result.warnings.append(f"{path}.data has no render_hints")


def validate_notes(result: ValidationResult, notes: Any) -> None:
    if not isinstance(notes, dict):
        result.errors.append("notes.json root must be an object")
        return
    for key in ("recipe_id", "topic"):
        require_non_empty_string(result, notes, key, "notes.json")
    for key in ("open_questions", "decisions"):
        value = notes.get(key)
        if not isinstance(value, list):
            result.errors.append(f"notes.json {key} must be an array")
    open_questions = notes.get("open_questions")
    if isinstance(open_questions, list) and open_questions:
        result.warnings.append(f"notes.open_questions count={len(open_questions)}")

    source_metadata = notes.get("source_notes", notes.get("research_basis"))
    if not isinstance(source_metadata, list) or not source_metadata:
        result.errors.append("notes.json must include source_notes or research_basis")

    for key, value in notes.items():
        if key == "checklist_modified" and value is not False:
            result.errors.append("notes.json checklist_modified must not be true")


def validate_pdf_facing_scripts(
    result: ValidationResult, outline: Any, prose: Any, tables_doc: Any, figures_doc: Any
) -> None:
    for path, value in iter_strings(
        {
            "report_outline.json": outline,
            "prose_blocks.json": prose,
            "tables.json": tables_doc,
            "vector_figures.json": figures_doc,
        }
    ):
        if UNSUPPORTED_SCRIPT_RE.search(value):
            result.errors.append(f"unsupported script in {path}")


def print_result(result: ValidationResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(
        f"{status} {result.recipe_id} files={result.files} sections={result.sections} "
        f"prose_blocks={result.prose_blocks} tables={result.tables} "
        f"figures={result.figures} warnings={len(result.warnings)}"
    )
    for warning in result.warnings:
        print(f"WARN {result.recipe_id} {warning}")
    for error in result.errors:
        print(f"FAIL {result.recipe_id} {error}")


def require_non_empty_string(
    result: ValidationResult, obj: dict[str, Any], key: str, path: str
) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        result.errors.append(f"{path}.{key} must be a non-empty string")


def check_unique_id(
    result: ValidationResult,
    seen_ids: set[str],
    value: Any,
    path: str,
    key: str,
) -> None:
    if not isinstance(value, str) or not value.strip():
        result.errors.append(f"{path}.{key} must be a non-empty string")
        return
    if value in seen_ids:
        result.errors.append(f"{path}.{key} duplicate {value!r}")
    seen_ids.add(value)


def outline_headings(outline: Any) -> set[str]:
    if not isinstance(outline, dict):
        return set()
    return {
        section.get("heading")
        for section in as_list(outline.get("sections"))
        if isinstance(section, dict) and isinstance(section.get("heading"), str)
    }


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def iter_strings(obj: Any, path: str = ""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else str(key)
            yield from iter_strings(value, next_path)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            yield from iter_strings(value, f"{path}[{idx}]")


if __name__ == "__main__":
    sys.exit(main())
