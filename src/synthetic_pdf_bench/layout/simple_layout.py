from __future__ import annotations

from reportlab.lib.pagesizes import letter

from synthetic_pdf_bench.generators.figures import make_raster_figure
from synthetic_pdf_bench.generators.tables import make_simple_table
from synthetic_pdf_bench.generators.text_content import sample_paragraph
from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock


def build_mvp_scene(seed: int = 123, dpi: int = 144) -> SceneGraph:
    width_pt, height_pt = letter
    scene = SceneGraph(doc_id=f"synthetic_{seed:06d}", seed=seed, dpi=dpi)
    scene.add_page(width_pt=width_pt, height_pt=height_pt)

    scene.add_block(
        Block(
            block_id="b000001",
            type="title",
            page_index=0,
            reading_order=1,
            bbox_pt=[72, 710, 540, 750],
            text="Synthetic Technical Report",
            markdown="# Synthetic Technical Report",
        )
    )
    scene.add_block(
        Block(
            block_id="b000002",
            type="heading",
            page_index=0,
            reading_order=2,
            bbox_pt=[72, 665, 540, 690],
            text="Overview",
            markdown="## Overview",
        )
    )
    scene.add_block(
        Block(
            block_id="b000003",
            type="paragraph",
            page_index=0,
            reading_order=3,
            bbox_pt=[72, 590, 540, 650],
            text=sample_paragraph(),
        )
    )
    figure = FigureBlock(
        block_id="b000004",
        page_index=0,
        reading_order=4,
        bbox_pt=[126, 390, 486, 560],
        figure_id="fig_001",
        kind="system_architecture",
        source_type="raster",
        png_path="truth/figures/fig_001.png",
    )
    scene.add_block(figure)
    caption = Block(
        block_id="b000005",
        type="caption",
        page_index=0,
        reading_order=5,
        bbox_pt=[126, 360, 486, 382],
        text="Figure 1: System architecture.",
        markdown="*Figure 1: System architecture.*",
    )
    scene.add_block(caption)
    figure.caption_block_id = caption.block_id
    figure.markdown_ref = "![Figure 1: System architecture](figures/fig_001.png)"
    figure.markdown = figure.markdown_ref

    table = make_simple_table(
        block_id="b000006",
        table_id="tbl_001",
        page_index=0,
        reading_order=6,
        bbox_pt=[72, 185, 540, 330],
    )
    scene.add_block(table)
    scene.add_block(
        Block(
            block_id="b000007",
            type="footer",
            page_index=0,
            reading_order=100,
            bbox_pt=[72, 42, 540, 58],
            text="Page 1",
            include_in_markdown=False,
        )
    )
    make_raster_figure(seed)
    return scene
