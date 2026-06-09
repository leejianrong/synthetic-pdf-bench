from __future__ import annotations

from synthetic_pdf_bench.layout.coordinates import pt_to_norm_bbox, pt_to_px_bbox
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock
from synthetic_pdf_bench.schema.truth import DocumentTruth, PageTruth, RenderedPage


class SceneGraph:
    def __init__(self, doc_id: str, seed: int, dpi: int = 144) -> None:
        self.doc_id = doc_id
        self.seed = seed
        self.dpi = dpi
        self.language_profile: dict = {"primary": "en"}
        self.metadata: dict = {}
        self.pages: list[PageTruth] = []

    def add_page(self, width_pt: float, height_pt: float) -> PageTruth:
        page = PageTruth(
            page_index=len(self.pages),
            page_number=len(self.pages) + 1,
            width_pt=width_pt,
            height_pt=height_pt,
        )
        self.pages.append(page)
        return page

    def add_block(self, block: Block | TableBlock | FigureBlock) -> Block | TableBlock | FigureBlock:
        page = self.pages[block.page_index]
        block.bbox_px = pt_to_px_bbox(block.bbox_pt, page.height_pt, self.dpi)
        block.bbox_norm = pt_to_norm_bbox(block.bbox_pt, page.width_pt, page.height_pt)
        if isinstance(block, TableBlock):
            for cell in block.cells:
                cell.bbox_px = pt_to_px_bbox(cell.bbox_pt, page.height_pt, self.dpi)
                cell.bbox_norm = pt_to_norm_bbox(cell.bbox_pt, page.width_pt, page.height_pt)
        page.blocks.append(block)
        return block

    def blocks_in_reading_order(self) -> list[Block | TableBlock | FigureBlock]:
        return sorted(
            (block for page in self.pages for block in page.blocks),
            key=lambda block: (block.page_index, block.reading_order, block.block_id),
        )

    def set_rendered_page(
        self, page_index: int, image_path: str, width_px: int | None = None, height_px: int | None = None
    ) -> None:
        page = self.pages[page_index]
        page.rendered_image = RenderedPage(
            page_index=page.page_index,
            page_number=page.page_number,
            image_path=image_path,
            width_px=width_px,
            height_px=height_px,
            dpi=self.dpi,
        )

    def to_truth(self) -> DocumentTruth:
        blocks = self.blocks_in_reading_order()
        return DocumentTruth(
            doc_id=self.doc_id,
            seed=self.seed,
            language_profile=self.language_profile,
            pages=self.pages,
            blocks=blocks,
            tables=[block for block in blocks if isinstance(block, TableBlock)],
            figures=[block for block in blocks if isinstance(block, FigureBlock)],
            metadata=self.metadata,
        )
