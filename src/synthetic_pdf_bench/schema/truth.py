from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock


class RenderedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int
    page_number: int
    image_path: str
    width_px: int | None = None
    height_px: int | None = None
    dpi: int


class PageTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int
    page_number: int
    width_pt: float
    height_pt: float
    rotation: int = 0
    rendered_image: RenderedPage | None = None
    blocks: list[TableBlock | FigureBlock | Block] = Field(default_factory=list)


class DocumentTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    seed: int
    source_pdf: str = "document.pdf"
    language_profile: dict[str, Any] = Field(default_factory=lambda: {"primary": "en"})
    pages: list[PageTruth] = Field(default_factory=list)
    blocks: list[TableBlock | FigureBlock | Block] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    figures: list[FigureBlock] = Field(default_factory=list)
    markdown_path: str = "truth/document.md"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "DocumentTruth":
        block_ids = {block.block_id for block in self.blocks}
        table_block_ids = {block.block_id for block in self.blocks if isinstance(block, TableBlock)}
        figure_block_ids = {block.block_id for block in self.blocks if isinstance(block, FigureBlock)}
        page_indices = {page.page_index for page in self.pages}

        for page in self.pages:
            for block in page.blocks:
                if block.page_index != page.page_index:
                    raise ValueError("page block has mismatched page_index")
                if block.block_id not in block_ids:
                    raise ValueError("page block is missing from top-level blocks")

        for block in self.blocks:
            if block.page_index not in page_indices:
                raise ValueError("block references missing page_index")

        for table in self.tables:
            if table.block_id not in table_block_ids:
                raise ValueError("top-level table is missing from blocks")

        for figure in self.figures:
            if figure.block_id not in figure_block_ids:
                raise ValueError("top-level figure is missing from blocks")
            if figure.caption_block_id is not None and figure.caption_block_id not in block_ids:
                raise ValueError("figure caption_block_id does not reference an existing block")

        return self
