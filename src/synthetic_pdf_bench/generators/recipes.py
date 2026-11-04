from __future__ import annotations

import json
import re
from pathlib import Path
from random import Random
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ParagraphRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["paragraph"]
    text: str
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergedCell(BaseModel):
    """A span anchored at (row, col) in the recipe matrix. The matrix still holds text for the covered positions."""

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    rowspan: int = Field(default=1, ge=1)
    colspan: int = Field(default=1, ge=1)


class TableRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["table"]
    table_id: str
    title: str = ""
    caption: str = ""
    caption_position: Literal["before", "after"] = "after"
    matrix: list[list[str]]
    merged_cells: list[MergedCell] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("matrix")
    @classmethod
    def validate_matrix(cls, matrix: list[list[str]]) -> list[list[str]]:
        if len(matrix) < 2:
            raise ValueError("table matrix must include a header row and at least one body row")
        widths = {len(row) for row in matrix}
        if len(widths) != 1:
            raise ValueError("table matrix must be rectangular")
        if next(iter(widths)) == 0:
            raise ValueError("table matrix rows cannot be empty")
        return matrix

    @model_validator(mode="after")
    def validate_merged_cells(self) -> TableRecipe:
        taken: set[tuple[int, int]] = set()
        for m in self.merged_cells:
            if m.row + m.rowspan > len(self.matrix) or m.col + m.colspan > len(self.matrix[0]):
                raise ValueError(f"merged cell at ({m.row}, {m.col}) extends past the table")
            if m.row == 0 and m.rowspan > 1:
                raise ValueError("a merged cell cannot span the header row into the body")
            covered = {(m.row + r, m.col + c) for r in range(m.rowspan) for c in range(m.colspan)}
            if covered & taken:
                raise ValueError(f"merged cell at ({m.row}, {m.col}) overlaps another merged cell")
            taken |= covered
        return self


class FigureRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["figure"]
    figure_id: str
    kind: str
    source_type: Literal["raster", "vector", "hybrid"] = "vector"
    title: str = ""
    caption: str
    caption_position: Literal["before", "after"] = "after"
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["list"]
    items: list[str]
    ordered: bool = False
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("items")
    @classmethod
    def validate_items(cls, items: list[str]) -> list[str]:
        if not items:
            raise ValueError("list must include at least one item")
        return items


class FootnoteRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["footnote"]
    text: str
    marker: str = ""
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["reference"]
    text: str
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class FormulaRecipe(BaseModel):
    """A display equation. ``latex`` is matplotlib mathtext, so it stays within \\frac, \\sqrt, \\sum, scripts and Greek letters."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["formula"]
    latex: str
    metadata: dict[str, Any] = Field(default_factory=dict)


RecipeBlock = ParagraphRecipe | TableRecipe | FigureRecipe | ListRecipe | FootnoteRecipe | ReferenceRecipe | FormulaRecipe


class SectionRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    blocks: list[RecipeBlock]
    page_break_before: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    language_profile: dict[str, Any] = Field(default_factory=lambda: {"primary": "en"})
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections: list[SectionRecipe]


def recipe_variant_names() -> list[str]:
    return ["standard", "compact", "spacious", "text_heavy", "figure_heavy", "table_heavy", "two_column", "random", "structured"]


_FORMULAS = [
    r"g = \frac{P_{t} - P_{t-1}}{P_{t-1}} \times 100",
    r"\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_{i}",
    r"\sigma = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (x_{i} - \bar{x})^{2}}",
    r"Y_{t} = \alpha + \beta X_{t} + \epsilon_{t}",
    r"r = \frac{\sum (x_{i} - \bar{x})(y_{i} - \bar{y})}{\sqrt{\sum (x_{i} - \bar{x})^{2} \sum (y_{i} - \bar{y})^{2}}}",
    r"V_{n} = V_{0} (1 + r)^{n}",
    r"\Delta = \frac{X_{2} - X_{1}}{X_{1}}",
    r"S = \sum_{k=1}^{m} w_{k} s_{k}",
]


def _structure(recipe: DocumentRecipe, seed: int) -> None:
    """Turn some paragraphs into paragraph + list, paragraph + footnote and paragraph + formula, in place.

    The recipes carry no lists, footnotes or equations, so layout models trained on them never see those classes.
    """
    rng = Random(seed)
    note = 0
    for section in recipe.sections:
        blocks: list[RecipeBlock] = []
        for block in section.blocks:
            blocks.append(block)
            if block.type != "paragraph":
                continue
            sentences = re.split(r"(?<=[.!?])\s+", block.text.strip())
            extra: list[RecipeBlock] = []
            if len(sentences) >= 3 and rng.random() < 0.6:
                keep = max(1, len(sentences) - 3)
                items = [s.rstrip(".") for s in sentences[keep:]]
                block.text, sentences = " ".join(sentences[:keep]), sentences[:keep]
                extra.append(ListRecipe(type="list", items=items, ordered=rng.random() < 0.5, language=block.language))
            if len(sentences) >= 3 and rng.random() < 0.3:
                note += 1
                block.text, tail = " ".join(sentences[:-1]), sentences[-1]
                extra.append(FootnoteRecipe(type="footnote", text=tail, marker=str(note), language=block.language))
            if rng.random() < 0.2:
                extra.append(FormulaRecipe(type="formula", latex=rng.choice(_FORMULAS)))
            blocks.extend(extra)
        section.blocks = blocks


def apply_recipe_variant(recipe: DocumentRecipe, variant: str, seed: int) -> DocumentRecipe:
    if variant not in recipe_variant_names():
        raise ValueError(f"unknown recipe variant: {variant}")
    copied = recipe.model_copy(deep=True)
    copied.doc_id = f"{recipe.doc_id}_{variant}_{seed:06d}"
    copied.metadata = {
        **copied.metadata,
        "base_doc_id": recipe.doc_id,
        "recipe_variant": variant,
        "variant_seed": seed,
    }
    if variant == "structured":
        _structure(copied, seed)
        return copied
    if variant in {"standard", "spacious", "two_column", "random"}:
        return copied

    for section_index, section in enumerate(copied.sections):
        paragraphs = [block for block in section.blocks if block.type == "paragraph"]
        tables = [block for block in section.blocks if block.type == "table"]
        figures = [block for block in section.blocks if block.type == "figure"]
        if variant == "compact":
            section.blocks = paragraphs[:2] + tables[:1] + figures[:1]
        elif variant == "text_heavy":
            section.blocks = paragraphs + tables[:1]
        elif variant == "figure_heavy":
            section.blocks = paragraphs[:2] + figures + tables[:1]
        elif variant == "table_heavy":
            keep_figure = figures[:1] if section_index % 2 == 0 else []
            section.blocks = paragraphs[:2] + tables + keep_figure
    return copied


def load_recipe(path: Path) -> DocumentRecipe:
    data = json.loads(path.read_text(encoding="utf-8"))
    return DocumentRecipe.model_validate(data)


def default_recipe_path() -> Path:
    return Path("data/recipes/canonical/sea_historical_report_v1.json")
