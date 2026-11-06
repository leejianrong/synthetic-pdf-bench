from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.layout.flow_layout import random_style
from synthetic_pdf_bench.render.fonts import FONT_FAMILIES
from synthetic_pdf_bench.schema.truth import DocumentTruth


def test_random_style_is_deterministic_and_diverse() -> None:
    assert random_style(7) == random_style(7)
    styles = {random_style(seed) for seed in range(30)}
    assert len(styles) == 30
    assert {s.columns for s in styles} == {1, 2}
    families = {s.font_family for s in styles}
    assert families <= set(FONT_FAMILIES) and len(families) >= 4
    assert len({s.page_size for s in styles}) == 2


def test_random_variant_records_its_template_in_truth(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=3, variant="random")
    truth = DocumentTruth.model_validate_json((tmp_path / "doc/truth/document.json").read_text())

    style = truth.metadata["layout_style"]
    assert style["font_family"] == random_style(3).font_family
    assert truth.pages[0].width_pt == random_style(3).page_size[0]


def test_page_furniture_never_overlaps(tmp_path: Path) -> None:
    for seed in range(1, 13):
        generate(tmp_path / str(seed), seed=seed, variant="random")
        truth = DocumentTruth.model_validate_json((tmp_path / str(seed) / "truth/document.json").read_text())
        for page in truth.pages:
            furniture = [b.bbox_pt for b in page.blocks if b.type in {"header", "footer", "page_number"}]
            for i, a in enumerate(furniture):
                for b in furniture[i + 1 :]:
                    assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (seed, a, b)
