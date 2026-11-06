from collections import Counter
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest
from reportlab.pdfgen.canvas import Canvas

from synthetic_pdf_bench.generators.recipes import load_recipe
from synthetic_pdf_bench.layout.flow_layout import (
    FlowLayoutPlanner,
    LayoutStyle,
    random_style,
)
from synthetic_pdf_bench.render.fonts import FONT_FAMILIES, font_for_text
from synthetic_pdf_bench.render.reportlab_renderer import ReportLabRenderer

NEW = ["DejaVuSans", "DejaVuSerif", "STIX", "ComputerModern"]
RECIPE = Path("data/recipes/canonical/sea_historical_report_v1.json")


def test_the_new_families_exist_with_a_bold_face() -> None:
    assert set(NEW) <= set(FONT_FAMILIES)
    assert all(FONT_FAMILIES[f][0] != FONT_FAMILIES[f][1] for f in NEW)


@pytest.mark.parametrize("family", NEW)
@pytest.mark.parametrize("bold", [False, True])
def test_text_in_every_family_can_be_read_back_from_the_pdf(tmp_path: Path, family: str, bold: bool) -> None:
    sentence = "Hello World, the quick brown fox jumps over 13 lazy dogs (1963-1965)."
    pdf = tmp_path / "t.pdf"
    canvas = Canvas(str(pdf))
    canvas.setFont(font_for_text(sentence, bold=bold, family=family), 11)
    canvas.drawString(72, 700, sentence)
    canvas.save()

    assert pymupdf.open(pdf)[0].get_text().strip() == sentence


def test_text_a_family_cannot_draw_falls_back_to_a_font_that_can() -> None:
    assert font_for_text("Les Néerlandais à Batavia, â", family="ComputerModern") not in {"cmr10", "cmb10"}
    assert font_for_text("plain ascii", family="ComputerModern") == "cmr10"  # but it keeps the family when it can


def test_styles_pick_families_in_roughly_the_real_proportions() -> None:
    fonts = Counter(random_style(seed).font_family for seed in range(1000))
    assert set(NEW) <= set(fonts)
    assert 0.35 < (fonts["Helvetica"] + fonts["Times"]) / 1000 < 0.6  # real: half of text is Helvetica or Times
    assert 0.08 < fonts["ComputerModern"] / 1000 < 0.2  # real: 14% LaTeX
    assert fonts["Courier"] < 0.05 * 1000


@pytest.mark.parametrize("family", NEW)
def test_a_page_in_each_family_renders_the_lines_the_truth_holds(tmp_path: Path, family: str) -> None:
    recipe = load_recipe(RECIPE)
    scene = FlowLayoutPlanner(seed=4, style=replace(LayoutStyle(), font_family=family)).build_scene(recipe)
    pdf = tmp_path / "doc.pdf"
    ReportLabRenderer(seed=4).render(scene.pages, pdf)

    page_text = " ".join(pymupdf.open(pdf)[0].get_text().split())
    lines = [line.text for b in scene.pages[0].blocks if b.type == "paragraph" for line in b.lines]
    assert lines and all(" ".join(line.split()) in page_text for line in lines)
