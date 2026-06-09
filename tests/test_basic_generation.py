from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate, generate_dataset


def test_basic_generation_outputs_expected_files(tmp_path: Path) -> None:
    output = tmp_path / "synthetic_000001"

    summary = generate(output, seed=123)

    assert (output / "document.pdf").is_file()
    assert (output / "truth" / "document.json").is_file()
    assert (output / "truth" / "document.md").is_file()
    assert (output / "truth" / "manifest.json").is_file()
    assert (output / "truth" / "pages" / "page_001.png").is_file()
    assert (output / "truth" / "figures" / "fig_001_regional_overview.png").is_file()
    assert "![Figure 1: Regional overview](figures/fig_001_regional_overview.png)" in (
        output / "truth" / "document.md"
    ).read_text(encoding="utf-8")
    assert "多元社会" in (output / "truth" / "document.md").read_text(encoding="utf-8")

    page_files = sorted((output / "truth" / "pages").glob("page_*.png"))
    figure_files = sorted((output / "truth" / "figures").glob("*.png"))
    assert 3 <= len(page_files) <= 8
    assert len(figure_files) >= 2
    assert summary["page_count"] == len(page_files)
    assert summary["recipe_variant"] == "standard"


def test_dataset_generation_outputs_manifest_and_documents(tmp_path: Path) -> None:
    output_root = tmp_path / "dataset"

    manifest = generate_dataset(
        output_root,
        count=3,
        seed_start=40,
        variants=["compact", "text_heavy", "figure_heavy"],
    )

    assert (output_root / "manifest.json").is_file()
    assert manifest["count"] == 3
    assert [doc["seed"] for doc in manifest["documents"]] == [40, 41, 42]
    assert [doc["recipe_variant"] for doc in manifest["documents"]] == ["compact", "text_heavy", "figure_heavy"]
    for index in range(1, 4):
        doc_dir = output_root / f"synthetic_{index:06d}"
        assert (doc_dir / "document.pdf").is_file()
        assert (doc_dir / "truth" / "document.json").is_file()
        assert (doc_dir / "truth" / "manifest.json").is_file()
