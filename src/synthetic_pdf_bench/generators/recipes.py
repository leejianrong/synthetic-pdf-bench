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
    matrix: list[list[str]]
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
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


RecipeBlock = ParagraphRecipe | TableRecipe | FigureRecipe


class SectionRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    blocks: list[RecipeBlock]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    language_profile: dict[str, Any] = Field(default_factory=lambda: {"primary": "en"})
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections: list[SectionRecipe]


def load_recipe(path: Path) -> DocumentRecipe:
    data = json.loads(path.read_text(encoding="utf-8"))
    return DocumentRecipe.model_validate(data)


def default_recipe_path() -> Path:
    return Path("data/recipes/sea_historical_report_v1.json")
