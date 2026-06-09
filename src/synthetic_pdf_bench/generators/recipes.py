from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParagraphRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["paragraph"]
    text: str
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TableRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["table"]
    table_id: str
    title: str = ""
    caption: str = ""
    caption_position: Literal["before", "after"] = "after"
    matrix: list[list[str]]
    merged_cells: list[dict[str, Any]] = Field(default_factory=list)
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


RecipeBlock = ParagraphRecipe | TableRecipe | FigureRecipe | ListRecipe | FootnoteRecipe | ReferenceRecipe


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


RecipeVariant = Literal["standard", "compact", "spacious", "text_heavy", "figure_heavy", "table_heavy", "two_column"]


def recipe_variant_names() -> list[str]:
    return ["standard", "compact", "spacious", "text_heavy", "figure_heavy", "table_heavy", "two_column"]


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
    if variant in {"standard", "spacious", "two_column"}:
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
    return Path("data/recipes/sea_historical_report_v1.json")
