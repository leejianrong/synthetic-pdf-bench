from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfbase import pdfmetrics

from synthetic_pdf_bench.generators.figures import make_raster_figure
from synthetic_pdf_bench.generators.recipes import (
    DocumentRecipe,
    FigureRecipe,
    FootnoteRecipe,
    ListRecipe,
    MergedCell,
    ReferenceRecipe,
    TableRecipe,
)
from synthetic_pdf_bench.generators.tables import table_to_html, table_to_markdown
from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.render.fonts import (
    FONT_FAMILIES,
    contains_cjk,
    font_for_text,
    register_fonts,
)
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock, TableCell

_CELL_PAD_X = 4  # table cell padding in points, recorded in table metadata for the renderer
_CELL_PAD_Y = 3



def _span_maps(spans: list[MergedCell]) -> tuple[dict[tuple[int, int], MergedCell], set[tuple[int, int]]]:
    """Anchor position -> span, and the positions each span covers besides its anchor."""
    anchors = {(m.row, m.col): m for m in spans}
    covered = {(m.row + r, m.col + c) for m in spans for r in range(m.rowspan) for c in range(m.colspan)} - set(anchors)
    return anchors, covered

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
    table_line_height: float = 8
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
    page_size: tuple[float, float] = letter
    font_family: str = "Helvetica"
    page_number_align: str = "right"


def random_style(seed: int) -> LayoutStyle:
    """Sample a whole page template (geometry, type, columns, page furniture) from ``seed``."""
    rng = random.Random(seed)
    body = rng.choice([8, 9, 10, 11])
    return LayoutStyle(
        margin_left=rng.randint(48, 80),
        margin_right=rng.randint(48, 80),
        margin_top=rng.randint(62, 84),
        margin_bottom=rng.randint(62, 84),
        title_font_size=rng.randint(16, 20),  # title/heading line heights are fixed at 22/16
        heading_font_size=rng.randint(11, 14),
        body_font_size=body,
        caption_font_size=max(7, body - 1),
        body_line_height=round(body * rng.uniform(1.2, 1.45), 1),
        block_spacing=rng.randint(6, 14),
        section_spacing=rng.randint(8, 18),
        table_row_height=rng.randint(15, 24),
        columns=rng.choice([1, 1, 2]),
        force_section_page_breaks=rng.random() < 0.25,
        page_size=rng.choice([letter, A4]),
        font_family=rng.choice(list(FONT_FAMILIES)),
        page_number_align=rng.choice(["left", "center", "right"]),
    )


def style_for_variant(variant: str, seed: int = 0) -> LayoutStyle:
    if variant == "random":
        return random_style(seed)
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
        self.page_width, self.page_height = self.style.page_size
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
        self.scene.metadata = {**recipe.metadata, "layout_style": asdict(self.style)}
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
        footer_text = "Synthetic benchmark document"
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
                bbox_pt=self._footer_bbox(footer_text),
                text=footer_text,
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
                bbox_pt=self._page_number_bbox(),
                text=f"Page {page_number}",
                include_in_markdown=False,
                metadata={"role": "page_number"},
            )
        )

    def _footer_bbox(self, text: str) -> list[float]:
        """Tight to the text, on the side opposite a left-aligned page number."""
        width = pdfmetrics.stringWidth(text, font_for_text(text), 8)
        x0 = self.style.margin_left
        if self.style.page_number_align == "left":
            x0 = self.page_width - self.style.margin_right - width
        return [x0, 38, x0 + width, 52]

    def _page_number_bbox(self) -> list[float]:
        left, right = self.style.margin_left, self.page_width - self.style.margin_right
        x0 = {"left": left, "center": (left + right) / 2 - 20, "right": right - 40}[self.style.page_number_align]
        return [x0, 38, x0 + 40, 52]

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
        spans = recipe.merged_cells
        col_widths = self._column_widths(recipe.matrix, spans)
        wrapped = [self._wrap_row(row, col_widths, i, spans) for i, row in enumerate(recipe.matrix)]
        heights = self._row_heights(wrapped, spans)
        first_body = 1
        segment_index = 1
        while first_body < len(recipe.matrix):
            available_height = max(0, self.cursor_y - self.content_bottom)
            fitted, used = 0, heights[0]
            for height in heights[first_body:]:
                if used + height > available_height:
                    break
                fitted, used = fitted + 1, used + height
            while fitted and any(m.row <= first_body + fitted - 1 < m.row + m.rowspan - 1 for m in spans):
                fitted -= 1  # never cut a row-spanning cell between segments
            if fitted < self.style.min_table_rows_per_segment - 1:
                self._advance_region()
                continue
            rows = [0, *range(first_body, first_body + fitted)]
            first_body += fitted
            body_rows_remaining = len(recipe.matrix) - first_body
            matrix = [recipe.matrix[i] for i in rows]
            table_id = recipe.table_id if segment_index == 1 and not body_rows_remaining else f"{recipe.table_id}_part_{segment_index:02d}"
            self._add_table_segment(
                recipe,
                table_id,
                matrix,
                segment_index,
                body_rows_remaining,
                [wrapped[i] for i in rows],
                [heights[i] for i in rows],
                col_widths,
                [m.model_copy(update={"row": rows.index(m.row)}) for m in spans if m.row in rows],
            )
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
        wrapped: list[list[list[str]]],
        row_heights: list[float],
        col_widths: list[float],
        spans: list[MergedCell],
    ) -> None:
        height = sum(row_heights)
        self._ensure_space(height + self.style.block_spacing)
        bbox = self._take_box(height)
        cells = self._table_cells(
            table_id, matrix, self._page_index, bbox, row_heights, col_widths, wrapped, spans
        )
        table = TableBlock(
            block_id=self._next_block_id(),
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            table_id=table_id,
            matrix=matrix,
            markdown=table_to_markdown(matrix),
            html=table_to_html(matrix, spans),
            cells=cells,
            metadata={
                **recipe.metadata,
                "title": recipe.title,
                "caption": recipe.caption,
                "merged_cells": [m.model_dump() for m in spans],
                "parent_table_id": recipe.table_id,
                "table_segment_index": segment_index,
                "body_rows_remaining": body_rows_remaining,
                "font_size": self.style.table_font_size,
                "line_height": self.style.table_line_height,
                "font_family": self.style.font_family,
                "cell_padding": [_CELL_PAD_X, _CELL_PAD_Y],
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

    def _column_widths(self, matrix: list[list[str]], spans: list[MergedCell]) -> list[float]:
        """Widths summing to the content width: each column at least as wide as its longest word when possible."""
        size, pad = self.style.table_font_size, 2 * _CELL_PAD_X
        longest, natural = [0.0] * len(matrix[0]), [0.0] * len(matrix[0])
        anchors, covered = _span_maps(spans)
        for row_idx, row in enumerate(matrix):
            for col, text in enumerate(row):
                if (row_idx, col) in covered or (m := anchors.get((row_idx, col))) and m.colspan > 1:
                    continue  # a wide cell fits the combined width instead of sizing one column
                font = font_for_text(text, bold=row_idx == 0, family=self.style.font_family)
                longest[col] = max(longest[col], *(pdfmetrics.stringWidth(t.strip(), font, size) for t in self._wrap_tokens(text)))
                natural[col] = max(natural[col], pdfmetrics.stringWidth(text, font, size))
        floor = [w + pad for w in longest]
        target = [max(n + pad, f) for n, f in zip(natural, floor, strict=True)]
        total = self.content_width
        if sum(target) <= total:
            widths = [w * total / sum(target) for w in target]
        elif sum(floor) >= total:
            widths = [w * total / sum(floor) for w in floor]  # narrower than the longest words; cells break words
        else:
            spare = (total - sum(floor)) / (sum(target) - sum(floor))
            widths = [f + (t - f) * spare for f, t in zip(floor, target, strict=True)]
        widths[-1] = total - sum(widths[:-1])  # exact sum, so cells stay inside the table bbox
        return widths

    def _wrap_row(self, row: list[str], col_widths: list[float], row_idx: int, spans: list[MergedCell]) -> list[list[str]]:
        anchors, covered = _span_maps(spans)
        size, bold = self.style.table_font_size, row_idx == 0
        wrapped = []
        for col, text in enumerate(row):
            if (row_idx, col) in covered:
                wrapped.append([""])
                continue
            colspan = m.colspan if (m := anchors.get((row_idx, col))) else 1
            width = sum(col_widths[col : col + colspan])
            wrapped.append(self._wrap_text(text, size, width - 2 * _CELL_PAD_X, bold, break_words=True))
        return wrapped

    def _row_heights(self, wrapped: list[list[list[str]]], spans: list[MergedCell]) -> list[float]:
        tall = {(m.row, m.col) for m in spans if m.rowspan > 1}
        heights = [self._row_height([w for c, w in enumerate(row) if (r, c) not in tall] or [[""]]) for r, row in enumerate(wrapped)]
        for m in spans:
            if m.rowspan > 1:  # grow the last spanned row if the cell's text needs more room
                shortfall = self._row_height([wrapped[m.row][m.col]]) - sum(heights[m.row : m.row + m.rowspan])
                heights[m.row + m.rowspan - 1] += max(0.0, shortfall)
        return heights

    def _row_height(self, wrapped_row: list[list[str]]) -> float:
        lines = max(len(cell_lines) for cell_lines in wrapped_row)
        style = self.style
        return max(style.table_row_height, 2 * _CELL_PAD_Y + style.table_font_size + (lines - 1) * style.table_line_height)

    def _table_cells(
        self,
        table_id: str,
        matrix: list[list[str]],
        page_index: int,
        bbox: list[float],
        row_heights: list[float],
        col_widths: list[float],
        wrapped: list[list[list[str]]],
        spans: list[MergedCell],
    ) -> list[TableCell]:
        x0, y1 = bbox[0], bbox[3]
        col_x = [x0 + sum(col_widths[:i]) for i in range(len(col_widths) + 1)]
        row_y = [y1 - sum(row_heights[:i]) for i in range(len(row_heights) + 1)]
        anchors, covered = _span_maps(spans)
        cells: list[TableCell] = []
        for row_idx, row in enumerate(matrix):
            for col_idx, text in enumerate(row):
                if (row_idx, col_idx) in covered:
                    continue
                m = anchors.get((row_idx, col_idx))
                rowspan, colspan = (m.rowspan, m.colspan) if m else (1, 1)
                cells.append(
                    TableCell(
                        cell_id=f"{table_id}_r{row_idx + 1:02d}c{col_idx + 1:02d}",
                        row=row_idx,
                        col=col_idx,
                        rowspan=rowspan,
                        colspan=colspan,
                        text=text,
                        bbox_pt=[col_x[col_idx], row_y[row_idx + rowspan], col_x[col_idx + colspan], row_y[row_idx]],
                        is_header=row_idx == 0,
                        metadata={"table_id": table_id, "lines": wrapped[row_idx][col_idx]},
                    )
                )
        return cells

    def _text_height(self, text: str, font_size: int, width: float, line_height: float, bold: bool = False) -> float:
        return len(self._wrap_text(text, font_size, width, bold)) * line_height

    def _wrap_text(self, text: str, font_size: int, width: float, bold: bool = False, break_words: bool = False) -> list[str]:
        font_name = font_for_text(text, bold=bold, family=self.style.font_family)
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
                while break_words and len(current) > 1 and pdfmetrics.stringWidth(current, font_name, font_size) > width:
                    cut = next(
                        (k for k in range(len(current) - 1, 0, -1) if pdfmetrics.stringWidth(current[:k], font_name, font_size) <= width),
                        1,
                    )
                    lines.append(current[:cut])
                    current = current[cut:]
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
            block.metadata = {
                **block.metadata,
                "font_size": typography[0],
                "line_height": typography[1],
                "font_family": self.style.font_family,
            }
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
    return FlowLayoutPlanner(seed=seed, dpi=dpi, style=style_for_variant(variant, seed)).build_scene(recipe)


def build_scene_from_recipe_path(path: Path, seed: int = 123, dpi: int = 144, variant: str = "standard") -> SceneGraph:
    from synthetic_pdf_bench.generators.recipes import apply_recipe_variant, load_recipe

    recipe = apply_recipe_variant(load_recipe(path), variant=variant, seed=seed)
    return build_scene_from_recipe(recipe, seed=seed, dpi=dpi, variant=variant)
