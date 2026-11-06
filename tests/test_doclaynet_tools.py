import gzip
import importlib.util
import json
import sys
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.schema.truth import DocumentTruth

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path("scripts") / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


survey = _load("doclaynet_survey")
analysis = _load("doclaynet_analysis")


def test_real_page_gives_each_text_cell_to_the_smallest_box_that_contains_it() -> None:
    row = {
        "metadata": {"coco_width": 1000, "coco_height": 1000, "original_width": 600.0, "original_height": 800.0, "doc_category": "manuals",
                     "collection": "c", "original_filename": "a.pdf", "page_no": 3, "num_pages": 9},
        "bboxes": [[100, 100, 500, 500], [150, 150, 100, 20]],  # a table with a text box inside it (xywh in pixels)
        "category_id": [9, 10],
        "pdf_cells": [[{"bbox": [160, 155, 80, 10], "text": "hello", "font": {"name": "ABCDEF+Helvetica-Bold"}},
                       {"bbox": [300, 400, 50, 10], "text": "cell", "font": {"name": "Times-Roman"}},
                       {"bbox": [900, 900, 10, 10], "text": "stray", "font": {"name": "Times-Roman"}}]],
    }

    page = survey.real_page(row, "train", 0)

    table, text = page["boxes"]
    assert (table[0], text[0]) == ("table", "text")
    assert (text[5], text[6], text[8]) == (1, 5, "Helvetica-Bold")  # the subset prefix is dropped
    assert (table[5], table[6]) == (1, 4)  # "cell" falls in the table only
    assert page["cells"] == 3 and page["chars"] == 14  # the stray cell counts for the page, not for a box
    assert text[7] == round(10 / 1000 * 800, 2)  # cell height in points


def test_synthetic_survey_counts_each_character_once(tmp_path: Path) -> None:
    generate_dataset(tmp_path / "ds", count=2, recipe_paths=RECIPES[:2], variants=["standard"])
    out = tmp_path / "survey.jsonl.gz"

    survey.synthetic(tmp_path / "ds", out)

    with gzip.open(out, "rt") as fh:
        pages = [json.loads(line) for line in fh]

    truth_chars = sum(
        len(line.text) for path in (tmp_path / "ds").glob("*/truth/document.json") for pg in DocumentTruth.model_validate_json(path.read_text()).pages
        for b in pg.blocks for line in getattr(b, "lines", None) or []
    )
    assert sum(box[6] for p in pages for box in p["boxes"]) == truth_chars  # was multiplied by the line count


def test_analysis_finds_no_gap_between_a_corpus_and_itself(tmp_path: Path) -> None:
    generate_dataset(tmp_path / "ds", count=3, recipe_paths=RECIPES[:3], variants=["standard", "structured"])
    out = tmp_path / "survey.jsonl.gz"
    survey.synthetic(tmp_path / "ds", out)
    corpus = analysis.Corpus()
    for page in analysis.read_pages(out):
        corpus.add(page)

    gaps = analysis.compare(corpus, corpus)

    assert corpus.n > 10 and gaps
    assert all(g["ks"] == 0.0 for g in gaps if g["ks"] is not None)


def test_the_bank_keeps_train_pages_of_a_few_documents_per_category(tmp_path: Path) -> None:
    def page(split: str, category: str, doc: str, n: int) -> str:
        return json.dumps({"split": split, "category": category, "doc": doc, "page_no": n, "boxes": [["text", 0, 0, 1, 1, 1, 1, 9.0, None]]}) + "\n"

    (tmp_path / "s").mkdir()
    with gzip.open(tmp_path / "s" / "x.jsonl.gz", "wt") as fh:
        for d in range(5):
            fh.write(page("train", "manuals", f"m{d}", 1) + page("train", "manuals", f"m{d}", 2))
        fh.write(page("train", "patents", "p0", 1) + page("test", "patents", "p1", 1) + page("validation", "manuals", "m9", 1))
        fh.write(json.dumps({"split": "train", "category": "patents", "doc": "p0", "page_no": 2, "boxes": []}) + "\n")  # an unannotated page

    survey.bank(tmp_path / "s", tmp_path / "bank.jsonl.gz", docs_per_category=2, seed=0)

    with gzip.open(tmp_path / "bank.jsonl.gz", "rt") as fh:
        pages = [json.loads(line) for line in fh]
    assert {p["split"] for p in pages} == {"train"}
    assert len({p["doc"] for p in pages if p["category"] == "manuals"}) == 2 and len([p for p in pages if p["category"] == "manuals"]) == 4
    assert [p["doc"] for p in pages if p["category"] == "patents"] == ["p0"]
    assert all(p["boxes"] for p in pages)  # the unannotated page of p0 is left out
