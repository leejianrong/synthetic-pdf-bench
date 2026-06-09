from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PredictedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    type: str
    page_index: int
    bbox_pt: list[float] | None = None
    text: str = ""
    markdown: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictedTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: str
    matrix: list[list[str]]
    page_index: int | None = None
    bbox_pt: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictedFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_id: str
    page_index: int | None = None
    bbox_pt: list[float] | None = None
    markdown_ref: str = ""
    png_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = ""
    markdown: str = ""
    blocks: list[PredictedBlock] = Field(default_factory=list)
    tables: list[PredictedTable] = Field(default_factory=list)
    figures: list[PredictedFigure] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
