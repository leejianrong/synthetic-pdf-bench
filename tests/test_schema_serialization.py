from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock
from synthetic_pdf_bench.schema.truth import DocumentTruth
from pydantic import ValidationError


def test_document_truth_serializes_round_trip() -> None:
    scene = SceneGraph(doc_id="doc", seed=1)
    scene.add_page(612, 792)
    scene.add_block(
        Block(
            block_id="b1",
            type="paragraph",
            page_index=0,
            reading_order=1,
            bbox_pt=[72, 100, 540, 130],
            text="Hello",
        )
    )

    truth = scene.to_truth()
    encoded = truth.model_dump_json()
    decoded = DocumentTruth.model_validate_json(encoded)

    assert decoded.doc_id == "doc"
    assert decoded.blocks[0].bbox_px == [144, 1324, 1080, 1384]
    assert decoded.pages[0].blocks[0].bbox_norm is not None


def test_invalid_bbox_is_rejected() -> None:
    try:
        Block(
            block_id="b1",
            type="paragraph",
            page_index=0,
            reading_order=1,
            bbox_pt=[10, 10, 5, 20],
        )
    except ValidationError:
        return
    raise AssertionError("invalid bbox should fail validation")


def test_document_truth_rejects_missing_figure_caption_link() -> None:
    figure = FigureBlock(
        block_id="b1",
        page_index=0,
        reading_order=1,
        bbox_pt=[0, 0, 10, 10],
        figure_id="fig_001",
        caption_block_id="missing",
    )
    try:
        DocumentTruth(
            doc_id="doc",
            seed=1,
            blocks=[figure],
            figures=[figure],
        )
    except ValidationError:
        return
    raise AssertionError("missing caption link should fail validation")
