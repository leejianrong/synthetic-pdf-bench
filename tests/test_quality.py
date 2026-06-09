from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate, generate_dataset
from synthetic_pdf_bench.quality import validate_generation
from synthetic_pdf_bench.schema.blocks import Block
from synthetic_pdf_bench.schema.truth import DocumentTruth, PageTruth


def test_generation_manifest_includes_quality_report(tmp_path: Path) -> None:
    output = tmp_path / "doc"
    summary = generate(output, seed=501)

    assert summary["quality"]["passed"] is True
    assert summary["quality"]["check_count"] >= 7
    assert summary["quality"]["visual_smoke"]["page_images_checked"] == summary["page_count"]
    assert summary["quality"]["visual_smoke"]["figure_crops_checked"] == summary["figure_count"]


def test_dataset_manifest_includes_summary_stats(tmp_path: Path) -> None:
    output_root = tmp_path / "dataset"
    manifest = generate_dataset(output_root, count=2, seed_start=600, variants=["compact", "two_column"])

    assert manifest["summary_stats"]["document_count"] == 2
    assert manifest["summary_stats"]["page_count"]["min"] >= 1
    assert manifest["summary_stats"]["variants"] == {"compact": 1, "two_column": 1}
    assert all(document["quality"]["passed"] for document in manifest["documents"])


def test_quality_validation_rejects_missing_markdown_span(tmp_path: Path) -> None:
    block = Block(
        block_id="b1",
        type="paragraph",
        page_index=0,
        reading_order=1,
        bbox_pt=[10, 10, 100, 30],
        text="hello",
        include_in_markdown=True,
    )
    truth = DocumentTruth(
        doc_id="bad",
        seed=1,
        pages=[PageTruth(page_index=0, page_number=1, width_pt=200, height_pt=200, blocks=[block])],
        blocks=[block],
    )

    try:
        validate_generation(tmp_path, truth, "hello")
    except ValueError as exc:
        assert "included_markdown_blocks_have_valid_spans" in str(exc)
        return
    raise AssertionError("missing markdown span should fail quality validation")
