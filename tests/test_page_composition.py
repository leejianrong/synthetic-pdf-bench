from collections import Counter
from pathlib import Path
from statistics import median

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.layout.flow_layout import LayoutStyle, random_style
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def _pages(root: Path):
    for path in sorted(root.glob("*/truth/document.json")):
        yield from DocumentTruth.model_validate_json(path.read_text()).pages


def _presence(root: Path) -> dict[str, float]:
    pages = list(_pages(root))
    seen = Counter(t for p in pages for t in {b.type for b in p.blocks})
    return {t: n / len(pages) for t, n in seen.items()}


def test_random_pages_have_the_real_share_of_captions_tables_and_pictures(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=14, recipe_paths=RECIPES, variants=["random"])
    share = _presence(tmp_path)
    # DocLayNet: caption on 18% of pages, table 26%, picture 29%. The generator gave 98%, 81% and 84%.
    assert share["caption"] < 0.5 and share["table"] < 0.5 and share["figure"] < 0.5


def test_documents_differ_in_which_page_furniture_they_have(tmp_path: Path) -> None:
    styles = [random_style(seed) for seed in range(300)]
    assert 0.35 < sum(s.has_header for s in styles) / 300 < 0.65  # real: a header on 49% of pages
    assert {s.footer_mode for s in styles} == {"none", "number", "text", "both"}
    assert len({s.furniture_font_size for s in styles}) > 4 and len({round(s.header_top) for s in styles}) > 10
    assert LayoutStyle().has_header and LayoutStyle().footer_mode == "both"  # the standard style is unchanged


def test_furniture_follows_the_document_style(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=14, recipe_paths=RECIPES, variants=["random"])
    counts = Counter()
    for page in _pages(tmp_path):
        counts["header"] += any(b.type == "header" for b in page.blocks)
        counts["footer"] += sum(b.type in {"footer", "page_number"} for b in page.blocks)
    pages = len(list(_pages(tmp_path)))
    assert counts["header"] < 0.8 * pages  # not on every page
    assert counts["footer"] < 1.7 * pages  # not two per page


def test_titles_and_headings_are_small_like_real_ones() -> None:
    styles = [random_style(seed) for seed in range(300)]
    assert median(s.title_font_size for s in styles) <= 14  # DocLayNet titles are 12.4 pt at the median
    assert median(s.heading_font_size for s in styles) <= 11  # section headers 10.9 pt
    assert all(s.title_line_height < 1.4 * s.title_font_size and s.heading_line_height < 1.4 * s.heading_font_size for s in styles)


def test_a_caption_box_is_as_tall_as_its_text_not_a_fixed_minimum(tmp_path: Path) -> None:
    generate_dataset(tmp_path, count=14, recipe_paths=RECIPES, variants=["random"])
    heights = [(b.bbox_pt[3] - b.bbox_pt[1]) / b.metadata["line_height"] / max(len(b.lines), 1) for p in _pages(tmp_path) for b in p.blocks if b.type == "caption" and b.lines]
    assert heights and median(heights) < 1.3  # DocLayNet captions are one to a few lines; ours had a 24 to 28 pt floor


def test_some_documents_run_the_full_title_in_the_page_header() -> None:
    from synthetic_pdf_bench.generators.recipes import load_recipe
    from synthetic_pdf_bench.layout.flow_layout import FlowLayoutPlanner

    assert {random_style(seed).header_text_mode for seed in range(100)} == {"short", "title"}
    recipe = load_recipe(RECIPES[0])
    scene = FlowLayoutPlanner(seed=1, style=LayoutStyle(header_text_mode="title")).build_scene(recipe)
    assert {b.text for p in scene.pages for b in p.blocks if b.type == "header"} == {recipe.title}
    short = FlowLayoutPlanner(seed=1).build_scene(recipe)
    assert {b.text for p in short.pages for b in p.blocks if b.type == "header"} == {recipe.title.split(":")[0]}
