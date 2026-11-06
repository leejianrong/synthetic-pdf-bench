import gzip
import json
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.export.coco import BLOCK_TYPE_TO_CATEGORY, export_coco
from synthetic_pdf_bench.generators.recipes import load_recipe
from synthetic_pdf_bench.layout.replay_layout import (
    build_replay_scene,
    load_layout_bank,
)

RECIPE = Path("data/recipes/canonical/sea_historical_report_v1.json")


def _page(doc: str, page_no: int, split: str = "train") -> dict:
    # [class, x, y, w, h, n_cells, n_chars, cell_h_pt, font], x y w h as page fractions with y down
    boxes = [["page-header", 0.1, 0.04, 0.2, 0.012, 1, 20, 9.0, "Helvetica"],
             ["section-header", 0.1, 0.1, 0.3, 0.015, 1, 24, 11.0, "Helvetica-Bold"],
             ["text", 0.1, 0.13, 0.8, 0.09, 6, 420, 9.0, "Times-Roman"],
             ["list-item", 0.1, 0.23, 0.7, 0.03, 2, 110, 9.0, "Times-Roman"],
             ["picture", 0.1, 0.28, 0.4, 0.2, 0, 0, None, None],
             ["caption", 0.1, 0.49, 0.4, 0.015, 1, 40, 8.0, "Times-Roman"],
             ["table", 0.1, 0.55, 0.8, 0.18, 30, 120, 8.0, "Helvetica"],
             ["formula", 0.1, 0.75, 0.3, 0.03, 1, 12, 9.0, None],
             ["footnote", 0.1, 0.9, 0.8, 0.02, 2, 90, 7.0, "Times-Roman"],
             ["page-footer", 0.45, 0.95, 0.05, 0.01, 1, 2, 9.0, "Helvetica"]]
    return {"split": split, "shard": 0, "category": "manuals", "collection": "c", "doc": doc, "page_no": page_no, "num_pages": 9,
            "w_pt": 612.0, "h_pt": 792.0, "cells": 0, "chars": 0, "boxes": boxes}


def _bank(tmp_path: Path) -> Path:
    path = tmp_path / "survey-0.jsonl.gz"
    with gzip.open(path, "wt") as fh:
        for doc, n, split in [("a.pdf", 1, "train"), ("a.pdf", 2, "train"), ("b.pdf", 1, "validation"), ("c.pdf", 5, "test")]:
            fh.write(json.dumps(_page(doc, n, split)) + "\n")
    return path


def test_the_bank_holds_train_layouts_only(tmp_path: Path) -> None:
    bank = load_layout_bank(_bank(tmp_path))
    assert set(bank) == {"a.pdf"} and len(bank["a.pdf"]) == 2  # validation and test pages never become training layouts


def test_every_bank_box_becomes_one_block_in_the_same_place(tmp_path: Path) -> None:
    pages = load_layout_bank(_bank(tmp_path))["a.pdf"]
    scene = build_replay_scene(load_recipe(RECIPE), pages, seed=3)

    assert len(scene.pages) == 2
    for page, source in zip(scene.pages, pages):
        assert (page.width_pt, page.height_pt) == (612.0, 792.0)
        assert sorted(BLOCK_TYPE_TO_CATEGORY[b.type] for b in page.blocks) == sorted(box[0] for box in source["boxes"])
        header = next(b for b in page.blocks if b.type == "header")
        x, y, w, h = source["boxes"][0][1:5]
        assert [round(v, 2) for v in header.bbox_pt] == [round(612 * x, 2), round(792 * (1 - y - h), 2), round(612 * (x + w), 2), round(792 * (1 - y), 2)]


def test_content_fits_inside_its_box(tmp_path: Path) -> None:
    scene = build_replay_scene(load_recipe(RECIPE), load_layout_bank(_bank(tmp_path))["a.pdf"], seed=3)
    for page in scene.pages:
        for b in page.blocks:
            x0, y0, x1, y1 = b.bbox_pt
            for line in getattr(b, "lines", None) or []:
                assert x0 - 0.5 <= line.bbox_pt[0] and line.bbox_pt[2] <= x1 + 0.5 and y0 - 0.5 <= line.bbox_pt[1] and line.bbox_pt[3] <= y1 + 0.5
            if b.type in {"paragraph", "list_item", "caption", "footnote"}:
                assert b.lines and b.text == " ".join(line.text for line in b.lines).replace("• ", "")  # the truth holds what was drawn
            if b.type == "table":
                assert b.cells and min(c.bbox_pt[0] for c in b.cells) == x0 and max(c.bbox_pt[2] for c in b.cells) == x1
                assert max(len(r) for r in b.matrix) >= 2 and len(b.matrix) >= 2
            if b.type == "formula":
                assert b.metadata["image_box"] == b.bbox_pt and b.metadata["number"] is None


def test_the_same_seed_gives_the_same_pages(tmp_path: Path) -> None:
    pages = load_layout_bank(_bank(tmp_path))["a.pdf"]
    one = build_replay_scene(load_recipe(RECIPE), pages, seed=5).to_truth().model_dump_json()
    two = build_replay_scene(load_recipe(RECIPE), pages, seed=5).to_truth().model_dump_json()
    other = build_replay_scene(load_recipe(RECIPE), pages, seed=6).to_truth().model_dump_json()
    assert one == two and one != other


def test_a_replay_document_renders_and_exports_the_banked_classes(tmp_path: Path) -> None:
    bank = _bank(tmp_path)
    out = tmp_path / "doc"
    generate(out, seed=3, recipe_path=RECIPE, variant="replay", layout_bank=bank)

    coco = export_coco(out)
    names = {c["id"]: c["name"] for c in coco["categories"]}
    counted = sorted(names[a["category_id"]] for a in coco["annotations"])
    expected = sorted(box[0] for p in load_layout_bank(bank)["a.pdf"] for box in p["boxes"])
    assert counted == expected
    assert (out / "document.pdf").exists() and len(coco["images"]) == 2


def test_a_table_whose_equal_columns_sum_past_its_edge_stays_inside_its_box() -> None:
    page = _page("a.pdf", 1)
    page["boxes"] = [["table", 0.2133575309085839, 0.3777542053798109, 0.36884279998456604, 0.33881284957875774, 5, 20, 8.681222265656285, "Helvetica"]]
    scene = build_replay_scene(load_recipe(RECIPE), [page], seed=9)  # this size made the cells overshoot by a rounding error
    (t,) = [b for b in scene.pages[0].blocks if b.type == "table"]
    assert all(t.bbox_pt[0] <= c.bbox_pt[0] and c.bbox_pt[2] <= t.bbox_pt[2] and t.bbox_pt[1] <= c.bbox_pt[1] and c.bbox_pt[3] <= t.bbox_pt[3] for c in t.cells)


def test_replayed_boxes_that_cross_are_kept_as_real_pages_have_them(tmp_path: Path) -> None:
    page = _page("a.pdf", 1)
    page["boxes"] = [["text", 0.1, 0.1, 0.5, 0.06, 3, 200, 9.0, "Times-Roman"], ["text", 0.4, 0.13, 0.5, 0.06, 3, 200, 9.0, "Times-Roman"]]  # they cross
    bank = tmp_path / "survey-x.jsonl.gz"
    with gzip.open(bank, "wt") as fh:
        fh.write(json.dumps(page) + "\n")
    out = tmp_path / "doc"

    generate(out, seed=1, recipe_path=RECIPE, variant="replay", layout_bank=bank)

    assert len(export_coco(out)["annotations"]) == 2


def test_pages_with_no_boxes_are_not_banked(tmp_path: Path) -> None:
    empty = _page("a.pdf", 3)
    empty["boxes"] = []  # DocLayNet has unannotated pages; replayed they would render blank
    path = tmp_path / "survey-e.jsonl.gz"
    with gzip.open(path, "wt") as fh:
        for page in [_page("a.pdf", 1), empty, _page("a.pdf", 4), {**empty, "doc": "only-empty.pdf"}]:
            fh.write(json.dumps(page) + "\n")

    bank = load_layout_bank(path)

    assert [p["page_no"] for p in bank["a.pdf"]] == [1, 4] and "only-empty.pdf" not in bank
