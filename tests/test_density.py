import re
from dataclasses import replace
from pathlib import Path
from statistics import median

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.export.coco import BLOCK_TYPE_TO_CATEGORY
from synthetic_pdf_bench.generators.recipes import load_recipe
from synthetic_pdf_bench.layout.flow_layout import (
    FlowLayoutPlanner,
    LayoutStyle,
    random_style,
)
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))
HISTORY = Path("data/recipes/canonical/singapore_history_1900_2020s_v1.json")  # forces a page break before each of 35 sections


def test_documents_rarely_start_every_section_on_a_new_page_and_may_ignore_recipe_breaks() -> None:
    styles = [random_style(seed) for seed in range(400)]
    assert sum(s.force_section_page_breaks for s in styles) / 400 < 0.12  # was 25%: the overflow of each section sat alone on a page
    assert all(0.0 <= s.honour_breaks <= 0.4 for s in styles)
    recipe = load_recipe(HISTORY)  # 5 of its 35 sections ask for a page break
    every = FlowLayoutPlanner(seed=3).build_scene(recipe)
    none = FlowLayoutPlanner(seed=3, style=replace(LayoutStyle(), honour_breaks=0.0)).build_scene(recipe)
    assert len(none.pages) < len(every.pages)


def test_random_pages_are_set_tighter_than_before() -> None:
    styles = [random_style(seed) for seed in range(300)]
    assert median(s.body_font_size for s in styles) <= 9
    assert all(s.body_line_height <= 1.36 * s.body_font_size for s in styles)
    assert median(s.block_spacing for s in styles) <= 7


def test_splitting_paragraphs_keeps_every_word_in_order() -> None:
    recipe = load_recipe(RECIPES[0])
    whole = FlowLayoutPlanner(seed=2).build_scene(recipe)
    split = FlowLayoutPlanner(seed=2, style=replace(LayoutStyle(), split_prob=1.0)).build_scene(recipe)

    def paragraphs(scene):
        return [b.text for p in scene.pages for b in p.blocks if b.type == "paragraph"]

    assert len(paragraphs(split)) > 1.3 * len(paragraphs(whole))
    assert " ".join(" ".join(paragraphs(split)).split()) == " ".join(" ".join(paragraphs(whole)).split())
    assert all(len(re.findall(r"[.!?](?:\s|$)", t)) <= 2 for t in paragraphs(split))


def test_reference_entries_are_list_items_as_in_real_bibliographies() -> None:
    assert BLOCK_TYPE_TO_CATEGORY["reference"] == "list-item"


def test_random_pages_hold_more_text(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=14, recipe_paths=RECIPES, variants=["random"])
    chars = [
        sum(len(line.text) for b in page.blocks for line in getattr(b, "lines", None) or [])
        for path in sorted(tmp_path.glob("*/truth/document.json"))
        for page in DocumentTruth.model_validate_json(path.read_text()).pages
    ]
    assert median(chars) > 1800  # DocLayNet median 2,308; the generator gave about 1,550
