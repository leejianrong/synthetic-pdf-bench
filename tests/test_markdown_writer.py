from synthetic_pdf_bench.markdown.writer import write_markdown
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock


def test_markdown_writer_assigns_spans() -> None:
    title = Block(
        block_id="b1",
        type="title",
        page_index=0,
        reading_order=1,
        bbox_pt=[0, 0, 10, 10],
        text="Doc",
    )
    figure = FigureBlock(
        block_id="b2",
        page_index=0,
        reading_order=2,
        bbox_pt=[0, 0, 10, 10],
        figure_id="fig_001",
        markdown_ref="![Figure 1: Caption](figures/fig_001.png)",
    )
    hidden = Block(
        block_id="b3",
        type="footer",
        page_index=0,
        reading_order=3,
        bbox_pt=[0, 0, 10, 10],
        text="hidden",
        include_in_markdown=False,
    )

    markdown = write_markdown([title, figure, hidden])

    assert markdown == "# Doc\n\n![Figure 1: Caption](figures/fig_001.png)\n"
    assert title.markdown_span == [0, 5]
    assert figure.markdown_span == [7, 48]
    assert hidden.markdown_span is None
