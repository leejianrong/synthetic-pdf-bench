from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BBox = list[float]
MarkdownSpan = list[int] | None


class TextWord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    bbox_pt: BBox
    bbox_px: BBox | None = None


class TextLine(BaseModel):
    """One drawn line of a text block. Boxes span ascent to descent of the font, so they are a little taller than the glyphs."""

    model_config = ConfigDict(extra="forbid")

    text: str
    bbox_pt: BBox
    bbox_px: BBox | None = None
    words: list[TextWord] = Field(default_factory=list)


class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    type: str
    subtype: str | None = None
    page_index: int
    reading_order: int
    bbox_pt: BBox
    bbox_px: BBox | None = None
    bbox_norm: BBox | None = None
    text: str = ""
    markdown: str = ""
    markdown_span: MarkdownSpan = None
    include_in_markdown: bool = True
    language: str = "en"
    lines: list[TextLine] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox_pt", "bbox_px", "bbox_norm")
    @classmethod
    def validate_bbox(cls, bbox: BBox | None) -> BBox | None:
        if bbox is None:
            return bbox
        if len(bbox) != 4:
            raise ValueError("bbox must contain four coordinates")
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bbox must satisfy x1 > x0 and y1 > y0")
        return bbox

    @field_validator("markdown_span")
    @classmethod
    def validate_markdown_span(cls, span: MarkdownSpan) -> MarkdownSpan:
        if span is None:
            return span
        if len(span) != 2:
            raise ValueError("markdown_span must contain [start, end]")
        start, end = span
        if start < 0 or end < start:
            raise ValueError("markdown_span must satisfy 0 <= start <= end")
        return span


class TableCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str
    bbox_pt: BBox
    bbox_px: BBox | None = None
    bbox_norm: BBox | None = None
    is_header: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox_pt", "bbox_px", "bbox_norm")
    @classmethod
    def validate_bbox(cls, bbox: BBox | None) -> BBox | None:
        if bbox is None:
            return bbox
        if len(bbox) != 4:
            raise ValueError("bbox must contain four coordinates")
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bbox must satisfy x1 > x0 and y1 > y0")
        return bbox


class TableBlock(Block):
    type: Literal["table"] = "table"
    table_id: str
    matrix: list[list[str]]
    html: str = ""
    cells: list[TableCell] = Field(default_factory=list)


class FigureBlock(Block):
    type: Literal["figure"] = "figure"
    figure_id: str
    kind: str = "figure"
    source_type: Literal["raster", "vector", "hybrid"] = "vector"
    png_path: str | None = None
    caption_block_id: str | None = None
    markdown_ref: str = ""
