from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate


def test_basic_generation_outputs_expected_files(tmp_path: Path) -> None:
    output = tmp_path / "synthetic_000001"

    generate(output, seed=123)

    assert (output / "document.pdf").is_file()
    assert (output / "truth" / "document.json").is_file()
    assert (output / "truth" / "document.md").is_file()
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
