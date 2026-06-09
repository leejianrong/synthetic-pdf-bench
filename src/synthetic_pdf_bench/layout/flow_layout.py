from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path

from reportlab.lib.pagesizes import letter

from synthetic_pdf_bench.generators.figures import make_raster_figure
from synthetic_pdf_bench.generators.recipes import DocumentRecipe, FigureRecipe, TableRecipe
from synthetic_pdf_bench.generators.tables import table_to_html, table_to_markdown
from synthetic_pdf_bench.layout.scene import SceneGraph
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
        self.reading_order = 0
        self.block_counter = 0
        self.figure_counter = 0

    @property
    def content_width(self) -> float:
        return self.page_width - self.style.margin_left - self.style.margin_right

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
            self._add_heading(section.heading, section.metadata)
            for recipe_block in section.blocks:
                if recipe_block.type == "paragraph":
                    self._add_paragraph(recipe_block.text, recipe_block.language, recipe_block.metadata)
                elif recipe_block.type == "table":
                    self._add_table(recipe_block)
                elif recipe_block.type == "figure":
                    self._add_figure(recipe_block)
        return self.scene

    def _new_page(self) -> None:
        assert self.scene is not None
        page = self.scene.add_page(width_pt=self.page_width, height_pt=self.page_height)
        self.cursor_y = self.page_height - self.style.margin_top - self.style.header_height
        self._add_page_furniture(page.page_index)

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
        height = self._text_height(title, self.style.title_font_size, self.content_width, line_height=22)
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
        height = self._text_height(heading, self.style.heading_font_size, self.content_width, line_height=16)
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

    def _add_table(self, recipe: TableRecipe) -> None:
        row_count = len(recipe.matrix)
        height = row_count * self.style.table_row_height
        total_height = height + self.style.table_caption_height + self.style.block_spacing
        self._ensure_space(total_height)
        bbox = self._take_box(height)
        cells = self._table_cells(recipe.table_id, recipe.matrix, self._page_index, bbox)
        table = TableBlock(
            block_id=self._next_block_id(),
            page_index=self._page_index,
            reading_order=self._next_reading_order(),
            bbox_pt=bbox,
            table_id=recipe.table_id,
            matrix=recipe.matrix,
            markdown=table_to_markdown(recipe.matrix),
            html=table_to_html(recipe.matrix),
            cells=cells,
            metadata={**recipe.metadata, "title": recipe.title, "caption": recipe.caption},
        )
        self._add_block(table)
        if recipe.caption:
            self._add_caption(recipe.caption, self.style.table_caption_height, {"caption_for": recipe.table_id, "caption_type": "table"})

    def _add_figure(self, recipe: FigureRecipe) -> None:
        height = self.style.figure_height
        total_height = height + self.style.figure_caption_height + self.style.block_spacing
        self._ensure_space(total_height)
        self.figure_counter += 1
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
        caption = self._add_caption(
            f"Figure {self.figure_counter}: {recipe.caption}",
            self.style.figure_caption_height,
            {"caption_for": recipe.figure_id},
        )
        figure.caption_block_id = caption.block_id

    def _add_caption(self, text: str, height: float, metadata: dict) -> Block:
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

    def _table_cells(self, table_id: str, matrix: list[list[str]], page_index: int, bbox: list[float]) -> list[TableCell]:
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
                cells.append(
                    TableCell(
                        cell_id=f"{table_id}_r{row_idx + 1:02d}c{col_idx + 1:02d}",
                        row=row_idx,
                        col=col_idx,
                        text=text,
                        bbox_pt=[cell_x0, cell_y0, cell_x1, cell_y1],
                        is_header=row_idx == 0,
                    )
                )
        return cells

    def _text_height(self, text: str, font_size: int, width: float, line_height: float) -> float:
        avg_char_width = font_size * 0.52
        chars_per_line = max(16, int(width / avg_char_width))
        line_count = max(1, ceil(len(text) / chars_per_line))
        return line_count * line_height

    def _ensure_space(self, height: float) -> None:
        if self.cursor_y - height < self.content_bottom:
            self._new_page()

    def _take_box(self, height: float, horizontal_inset: float = 0) -> list[float]:
        x0 = self.style.margin_left + horizontal_inset
        x1 = self.page_width - self.style.margin_right - horizontal_inset
        y1 = self.cursor_y
        y0 = y1 - height
        self.cursor_y = y0 - self.style.block_spacing
        return [x0, y0, x1, y1]

    def _add_block(self, block: Block | TableBlock | FigureBlock) -> None:
        assert self.scene is not None
        self.scene.add_block(block)

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


def build_scene_from_recipe(
    recipe: DocumentRecipe, seed: int = 123, dpi: int = 144, variant: str = "standard"
) -> SceneGraph:
    return FlowLayoutPlanner(seed=seed, dpi=dpi, style=style_for_variant(variant)).build_scene(recipe)


def build_scene_from_recipe_path(path: Path, seed: int = 123, dpi: int = 144, variant: str = "standard") -> SceneGraph:
    from synthetic_pdf_bench.generators.recipes import apply_recipe_variant, load_recipe

    recipe = apply_recipe_variant(load_recipe(path), variant=variant, seed=seed)
    return build_scene_from_recipe(recipe, seed=seed, dpi=dpi, variant=variant)
