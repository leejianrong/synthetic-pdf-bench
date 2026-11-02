from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics

from synthetic_pdf_bench.generators.figures import make_raster_figure
from synthetic_pdf_bench.generators.recipes import (
    DocumentRecipe,
    FigureRecipe,
    FootnoteRecipe,
    ListRecipe,
    ReferenceRecipe,
    TableRecipe,
)
from synthetic_pdf_bench.generators.tables import table_to_html, table_to_markdown
from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.render.fonts import contains_cjk, font_for_text, register_fonts
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock, TableCell


@dataclass(frozen=True)
class LayoutStyle:
    margin_left: float = 58
    margin_right: float = 58
    margin_top: float = 70
    margin_bottom: float = 70
    header_height: float = 24
    footer_height: float = 24
    title_font_size: int = 18
    heading_font_size: int = 13
    body_font_size: int = 9
    caption_font_size: int = 8
    table_font_size: int = 7
    body_line_height: float = 12
    block_spacing: float = 10
    section_spacing: float = 12
    table_row_height: float = 19
    table_caption_height: float = 24
    figure_height: float = 148
    figure_caption_height: float = 28
    raster_figure_height: float = 130
    columns: int = 1
    column_gutter: float = 24
    min_table_rows_per_segment: int = 2
    force_section_page_breaks: bool = False


def style_for_variant(variant: str) -> LayoutStyle:
    if variant == "compact":
        return LayoutStyle(
            margin_left=50,
            margin_right=50,
            margin_top=62,
            margin_bottom=62,
            body_font_size=8,
            body_line_height=10,
            block_spacing=6,
            section_spacing=8,
            table_row_height=16,
            table_caption_height=20,
            figure_height=124,
            figure_caption_height=24,
            raster_figure_height=110,
        )
    if variant == "spacious":
        return LayoutStyle(
            margin_left=70,
            margin_right=70,
            margin_top=78,
            margin_bottom=78,
            body_font_size=10,
            body_line_height=14,
            block_spacing=13,
            section_spacing=16,
            table_row_height=22,
            table_caption_height=28,
            figure_height=166,
            figure_caption_height=32,
            raster_figure_height=145,
        )
    if variant == "two_column":
        return LayoutStyle(
            margin_left=50,
            margin_right=50,
            margin_top=66,
            margin_bottom=66,
            body_font_size=8,
            body_line_height=10,
            block_spacing=6,
            section_spacing=9,
            table_row_height=15,
            table_caption_height=20,
            figure_height=112,
            figure_caption_height=22,
            raster_figure_height=96,
            columns=2,
            column_gutter=24,
        )
    if variant == "figure_heavy":
        return LayoutStyle(figure_height=166, raster_figure_height=145, block_spacing=8)
    if variant == "table_heavy":
        return LayoutStyle(table_row_height=17, table_caption_height=22, body_font_size=8, body_line_height=11)
    if variant == "text_heavy":
        return LayoutStyle(body_font_size=9, body_line_height=12, figure_height=128, raster_figure_height=110)
    return LayoutStyle()


class FlowLayoutPlanner:
    def __init__(self, seed: int = 123, dpi: int = 144, style: LayoutStyle | None = None) -> None:
        self.seed = seed
        self.dpi = dpi
        self.style = style or LayoutStyle()
        self.page_width, self.page_height = letter
        self.scene: SceneGraph | None = None
        self.cursor_y = 0.0
        self.column_index = 0
        self.reading_order = 0
        self.block_counter = 0
        self.figure_counter = 0
        register_fonts()

    @property
    def content_width(self) -> float:
        full_width = self.page_width - self.style.margin_left - self.style.margin_right
        return (full_width - self.style.column_gutter * (self.style.columns - 1)) / self.style.columns

    @property
    def content_bottom(self) -> float:
        return self.style.margin_bottom + self.style.footer_height

    def build_scene(self, recipe: DocumentRecipe) -> SceneGraph:
        self.scene = SceneGraph(doc_id=recipe.doc_id, seed=self.seed, dpi=self.dpi)
        self.scene.language_profile = recipe.language_profile
        self.scene.metadata = recipe.metadata
        self._new_page()
        self._add_title(recipe.title, recipe.metadata)
        self._add_raster_overview(recipe)
        for section in recipe.sections:
            if section.page_break_before or self.style.force_section_page_breaks or section.metadata.get("page_break_before"):
                self._advance_page()
            self._add_heading(section.heading, section.metadata)
            for recipe_block in section.blocks:
                if recipe_block.type == "paragraph":
                    self._add_paragraph(recipe_block.text, recipe_block.language, recipe_block.metadata)
                elif recipe_block.type == "list":
                    self._add_list(recipe_block)
                elif recipe_block.type == "table":
                    self._add_table(recipe_block)
                elif recipe_block.type == "figure":
                    self._add_figure(recipe_block)
                elif recipe_block.type == "footnote":
                    self._add_note(recipe_block)
                elif recipe_block.type == "reference":
                    self._add_reference(recipe_block)
        self.validate_layout()
        return self.scene

    def _new_page(self) -> None:
        assert self.scene is not None
        page = self.scene.add_page(width_pt=self.page_width, height_pt=self.page_height)
        self.column_index = 0
        self.cursor_y = self.page_height - self.style.margin_top - self.style.header_height
        self._add_page_furniture(page.page_index)

    def _advance_page(self) -> None:
        self._new_page()

    def _advance_region(self) -> None:
        if self.column_index + 1 < self.style.columns:
            self.column_index += 1
            self.cursor_y = self.page_height - self.style.margin_top - self.style.header_height
            return
        self._advance_page()

    def _add_page_furniture(self, page_index: int) -> None:
        assert self.scene is not None
        page_number = page_index + 1
        header_text = "Singapore, Malaysia, and Indonesia since 1900"
        self.scene.add_block(
            Block(
                block_id=self._next_block_id(),
                type="header",
                page_index=page_index,
                reading_order=-1000 + page_index,
                bbox_pt=[
                    self.style.margin_left,
                    self.page_height - 50,
                    self.page_width - self.style.margin_right,
                    self.page_height - 34,
                ],
                text=header_text,
                include_in_markdown=False,
                metadata={"role": "repeated_header"},
            )
        )
        self.scene.add_block(
            Block(
                block_id=self._next_block_id(),
                type="footer",
                page_index=page_index,
                reading_order=100000 + page_index,
                bbox_pt=[self.style.margin_left, 38, self.page_width - self.style.margin_right, 52],
                text="Synthetic benchmark document",
                include_in_markdown=False,
                metadata={"role": "repeated_footer"},
            )
        )
        self.scene.add_block(
            Block(
                block_id=self._next_block_id(),
                type="page_number",
                page_index=page_index,
                reading_order=100100 + page_index,
                bbox_pt=[self.page_width - self.style.margin_right - 40, 38, self.page_width - self.style.margin_right, 52],
                text=f"Page {page_number}",
                include_in_markdown=False,
                metadata={"role": "page_number"},
            )
        )

    def _add_title(self, title: str, metadata: dict) -> None:
        height = self._text_height(title, self.style.title_font_size, self.content_width, line_height=22, bold=True)
        self._ensure_space(height + self.style.section_spacing)
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="title",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text=title,
                markdown=f"# {title}",
                metadata=metadata,
            )
        )

    def _add_raster_overview(self, recipe: DocumentRecipe) -> None:
        make_raster_figure(self.seed)
        height = self.style.raster_figure_height
        self._ensure_space(height + self.style.figure_caption_height + self.style.block_spacing)
        self.figure_counter += 1
        figure_id = f"fig_{self.figure_counter:03d}_regional_overview"
        bbox = self._take_box(height, horizontal_inset=36)
        figure = FigureBlock(
            block_id=self._next_block_id(),
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            figure_id=figure_id,
            kind="regional_overview",
            source_type="raster",
            png_path=f"truth/figures/{figure_id}.png",
            markdown_ref=f"![Figure {self.figure_counter}: Regional overview](figures/{figure_id}.png)",
            markdown=f"![Figure {self.figure_counter}: Regional overview](figures/{figure_id}.png)",
            metadata={"source_notes": recipe.metadata.get("source_notes", []), "layout_role": "auto_raster_overview"},
        )
        self._add_block(figure)
        caption = self._add_caption(
            f"Figure {self.figure_counter}: Regional overview of Singapore, Malaysia, and Indonesia.",
            self.style.figure_caption_height,
            {"caption_for": figure.figure_id},
        )
        figure.caption_block_id = caption.block_id

    def _add_heading(self, heading: str, metadata: dict) -> None:
        height = self._text_height(heading, self.style.heading_font_size, self.content_width, line_height=16, bold=True)
        self._ensure_space(height + self.style.section_spacing)
        self.cursor_y -= self.style.section_spacing
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="heading",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text=heading,
                markdown=f"## {heading}",
                metadata=metadata,
            )
        )

    def _add_paragraph(self, text: str, language: str, metadata: dict) -> None:
        height = self._text_height(text, self.style.body_font_size, self.content_width, self.style.body_line_height)
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="paragraph",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text=text,
                language=language,
                metadata=metadata,
            )
        )

    def _add_list(self, recipe: ListRecipe) -> None:
        lines: list[str] = []
        for idx, item in enumerate(recipe.items, start=1):
            marker = f"{idx}." if recipe.ordered else "-"
            lines.append(f"{marker} {item}")
        markdown = "\n".join(lines)
        height = self._text_height(markdown, self.style.body_font_size, self.content_width, self.style.body_line_height)
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="list",
                subtype="ordered" if recipe.ordered else "unordered",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text="\n".join(recipe.items),
                markdown=markdown,
                language=recipe.language,
                metadata=recipe.metadata,
            )
        )

    def _add_table(self, recipe: TableRecipe) -> None:
        if recipe.caption and recipe.caption_position == "before":
            self._add_caption(recipe.caption, self.style.table_caption_height, {"caption_for": recipe.table_id, "caption_type": "table"})
        header = recipe.matrix[0]
        body_rows = recipe.matrix[1:]
        segment_index = 1
        while body_rows:
            available_height = max(0, self.cursor_y - self.content_bottom)
            available_rows = int(available_height // self.style.table_row_height)
            if available_rows < self.style.min_table_rows_per_segment:
                self._advance_region()
                continue
            max_body_rows = max(1, available_rows - 1)
            segment_rows = body_rows[:max_body_rows]
            body_rows = body_rows[max_body_rows:]
            matrix = [header] + segment_rows
            table_id = recipe.table_id if segment_index == 1 and not body_rows else f"{recipe.table_id}_part_{segment_index:02d}"
            self._add_table_segment(recipe, table_id, matrix, segment_index, body_rows_remaining=len(body_rows))
            segment_index += 1
        if recipe.caption and recipe.caption_position == "after":
            self._add_caption(recipe.caption, self.style.table_caption_height, {"caption_for": recipe.table_id, "caption_type": "table"})

    def _add_table_segment(
        self,
        recipe: TableRecipe,
        table_id: str,
        matrix: list[list[str]],
        segment_index: int,
        body_rows_remaining: int,
    ) -> None:
        height = len(matrix) * self.style.table_row_height
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        cells = self._table_cells(table_id, matrix, self._page_index, bbox, recipe.merged_cells)
        table = TableBlock(
            block_id=self._next_block_id(),
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            table_id=table_id,
            matrix=matrix,
            markdown=table_to_markdown(matrix),
            html=table_to_html(matrix),
            cells=cells,
            metadata={
                **recipe.metadata,
                "title": recipe.title,
                "caption": recipe.caption,
                "merged_cells": recipe.merged_cells,
                "parent_table_id": recipe.table_id,
                "table_segment_index": segment_index,
                "body_rows_remaining": body_rows_remaining,
            },
        )
        self._add_block(table)

    def _add_figure(self, recipe: FigureRecipe) -> None:
        height = self.style.figure_height
        total_height = height + self.style.figure_caption_height + self.style.block_spacing
        self._ensure_space(total_height)
        self.figure_counter += 1
        caption: Block | None = None
        if recipe.caption_position == "before":
            caption = self._add_caption(
                f"Figure {self.figure_counter}: {recipe.caption}",
                self.style.figure_caption_height,
                {"caption_for": recipe.figure_id},
            )
        bbox = self._take_box(height, horizontal_inset=18)
        figure = FigureBlock(
            block_id=self._next_block_id(),
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            figure_id=recipe.figure_id,
            kind=recipe.kind,
            source_type=recipe.source_type,
            png_path=f"truth/figures/{recipe.figure_id}.png",
            markdown_ref=f"![Figure {self.figure_counter}: {recipe.title or recipe.kind}](figures/{recipe.figure_id}.png)",
            markdown=f"![Figure {self.figure_counter}: {recipe.title or recipe.kind}](figures/{recipe.figure_id}.png)",
            metadata={**recipe.metadata, "title": recipe.title, "data": recipe.data},
        )
        self._add_block(figure)
        if caption is None:
            caption = self._add_caption(
                f"Figure {self.figure_counter}: {recipe.caption}",
                self.style.figure_caption_height,
                {"caption_for": recipe.figure_id},
            )
        figure.caption_block_id = caption.block_id

    def _add_note(self, recipe: FootnoteRecipe) -> None:
        marker = recipe.marker or "*"
        text = f"{marker} {recipe.text}"
        height = self._text_height(text, self.style.caption_font_size, self.content_width, self.style.body_line_height)
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="footnote",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text=text,
                markdown=text,
                language=recipe.language,
                metadata=recipe.metadata,
            )
        )

    def _add_reference(self, recipe: ReferenceRecipe) -> None:
        height = self._text_height(recipe.text, self.style.caption_font_size, self.content_width, self.style.body_line_height)
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        self._add_block(
            Block(
                block_id=self._next_block_id(),
                type="reference",
                page_index=self._page_index,
                reading_order=self._next_reading_order(),
                bbox_pt=bbox,
                text=recipe.text,
                markdown=recipe.text,
                language=recipe.language,
                metadata=recipe.metadata,
            )
        )

    def _add_caption(self, text: str, height: float, metadata: dict) -> Block:
        height = max(height, self._text_height(text, self.style.caption_font_size, self.content_width, self.style.body_line_height))
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        caption = Block(
            block_id=self._next_block_id(),
            type="caption",
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            text=text,
            markdown=f"*{text.rstrip('.')}.*",
            metadata=metadata,
        )
        self._add_block(caption)
        return caption

    def _table_cells(
        self, table_id: str, matrix: list[list[str]], page_index: int, bbox: list[float], merged_cells: list[dict] | None = None
    ) -> list[TableCell]:
        x0, y0, x1, y1 = bbox
        row_count = len(matrix)
        col_count = len(matrix[0])
        row_h = (y1 - y0) / row_count
        col_w = (x1 - x0) / col_count
        cells: list[TableCell] = []
        for row_idx, row in enumerate(matrix):
            for col_idx, text in enumerate(row):
                cell_x0 = x0 + col_idx * col_w
                cell_x1 = cell_x0 + col_w
                cell_y1 = y1 - row_idx * row_h
                cell_y0 = cell_y1 - row_h
                span = self._span_for_cell(row_idx, col_idx, merged_cells or [])
                cells.append(
                    TableCell(
                        cell_id=f"{table_id}_r{row_idx + 1:02d}c{col_idx + 1:02d}",
                        row=row_idx,
                        col=col_idx,
                        rowspan=span["rowspan"],
                        colspan=span["colspan"],
                        text=text,
                        bbox_pt=[cell_x0, cell_y0, cell_x1, cell_y1],
                        is_header=row_idx == 0,
                        metadata=self._cell_metadata(table_id, span),
                    )
                )
        return cells

    def _span_for_cell(self, row_idx: int, col_idx: int, merged_cells: list[dict]) -> dict:
        for span in merged_cells:
            if span.get("row") == row_idx and span.get("col") == col_idx:
                return {
                    "span_kind": "merged_approximation",
                    "rowspan": int(span.get("rowspan", 1)),
                    "colspan": int(span.get("colspan", 1)),
                    "text": span.get("text", ""),
                }
        return {"span_kind": "regular", "rowspan": 1, "colspan": 1}

    def _cell_metadata(self, table_id: str, span: dict) -> dict:
        return {"table_id": table_id, **span}

    def _text_height(self, text: str, font_size: int, width: float, line_height: float, bold: bool = False) -> float:
        return len(self._wrap_text(text, font_size, width, bold)) * line_height

    def _wrap_text(self, text: str, font_size: int, width: float, bold: bool = False) -> list[str]:
        font_name = font_for_text(text, bold=bold)
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            tokens = self._wrap_tokens(paragraph)
            current = ""
            for token in tokens:
                candidate = token if not current else current + token
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
                    current = candidate
                    continue
                if current:
                    lines.append(current.strip())
                current = token.lstrip()
            if current:
                lines.append(current.strip())
            elif not tokens:
                lines.append("")
        return lines or [""]

    def _wrap_tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        current = ""
        for char in text:
            if contains_cjk(char):
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
            elif char.isspace():
                current += char
                tokens.append(current)
                current = ""
            else:
                current += char
        if current:
            tokens.append(current)
        return tokens

    def _ensure_space(self, height: float) -> None:
        if self.cursor_y - height < self.content_bottom:
            self._advance_region()

    def _take_box(self, height: float, horizontal_inset: float = 0) -> list[float]:
        column_x0 = self.style.margin_left + self.column_index * (self.content_width + self.style.column_gutter)
        x0 = column_x0 + horizontal_inset
        x1 = column_x0 + self.content_width - horizontal_inset
        y1 = self.cursor_y
        y0 = y1 - height
        self.cursor_y = y0 - self.style.block_spacing
        return [x0, y0, x1, y1]

    def _add_block(self, block: Block | TableBlock | FigureBlock) -> None:
        assert self.scene is not None
        typography = self._typography(block.type)
        if typography is not None:
            # The renderer draws with exactly the metrics used to size the box.
            block.metadata = {**block.metadata, "font_size": typography[0], "line_height": typography[1]}
        self.scene.add_block(block)

    def _typography(self, block_type: str) -> tuple[int, float] | None:
        style = self.style
        return {
            "title": (style.title_font_size, 22),
            "heading": (style.heading_font_size, 16),
            "paragraph": (style.body_font_size, style.body_line_height),
            "list": (style.body_font_size, style.body_line_height),
            "caption": (style.caption_font_size, style.body_line_height),
            "footnote": (style.caption_font_size, style.body_line_height),
            "reference": (style.caption_font_size, style.body_line_height),
        }.get(block_type)

    @property
    def _page_index(self) -> int:
        assert self.scene is not None
        return len(self.scene.pages) - 1

    def _next_block_id(self) -> str:
        self.block_counter += 1
        return f"b{self.block_counter:06d}"

    def _next_reading_order(self) -> int:
        self.reading_order += 1
        return self.reading_order

    def validate_layout(self) -> None:
        assert self.scene is not None
        for page in self.scene.pages:
            content_blocks = [
                block
                for block in page.blocks
                if block.type not in {"header", "footer", "page_number"}
            ]
            for block in page.blocks:
                x0, y0, x1, y1 = block.bbox_pt
                if x0 < 0 or y0 < 0 or x1 > page.width_pt or y1 > page.height_pt:
                    raise ValueError(f"block {block.block_id} is outside page bounds")
            for index, block_a in enumerate(content_blocks):
                for block_b in content_blocks[index + 1 :]:
                    if self._boxes_overlap(block_a.bbox_pt, block_b.bbox_pt):
                        raise ValueError(f"blocks {block_a.block_id} and {block_b.block_id} overlap")

    def _boxes_overlap(self, box_a: list[float], box_b: list[float]) -> bool:
        ax0, ay0, ax1, ay1 = box_a
        bx0, by0, bx1, by1 = box_b
        return max(ax0, bx0) < min(ax1, bx1) and max(ay0, by0) < min(ay1, by1)


def build_scene_from_recipe(
    recipe: DocumentRecipe, seed: int = 123, dpi: int = 144, variant: str = "standard"
) -> SceneGraph:
    return FlowLayoutPlanner(seed=seed, dpi=dpi, style=style_for_variant(variant)).build_scene(recipe)


def build_scene_from_recipe_path(path: Path, seed: int = 123, dpi: int = 144, variant: str = "standard") -> SceneGraph:
    from synthetic_pdf_bench.generators.recipes import apply_recipe_variant, load_recipe

    recipe = apply_recipe_variant(load_recipe(path), variant=variant, seed=seed)
    return build_scene_from_recipe(recipe, seed=seed, dpi=dpi, variant=variant)
