import json
from pathlib import Path

import pytest

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.splits import assign_splits, write_coco_splits

RATIOS = {"train": 0.6, "val": 0.2, "test": 0.2}


def _docs(recipes: int, per_recipe: int) -> list[dict]:
    return [
        {"doc_id": f"d{r}_{i}", "recipe_path": f"recipe{r}.json", "metadata": {"layout_style": {"columns": r % 2}}}
        for r in range(recipes)
        for i in range(per_recipe)
    ]


def test_recipes_never_straddle_splits_and_every_doc_is_assigned_once() -> None:
    docs = _docs(recipes=7, per_recipe=3)

    splits = assign_splits(docs, RATIOS, "recipe", seed=1)

    assigned = [d for ids in splits.values() for d in ids]
    assert sorted(assigned) == sorted(d["doc_id"] for d in docs)
    assert all(splits.values())
    recipes_in = [{i.split("_")[0] for i in ids} for ids in splits.values()]
    assert sum(len(r) for r in recipes_in) == len(set().union(*recipes_in)) == 7  # no recipe in two splits


def test_assignment_is_deterministic_per_seed() -> None:
    docs = _docs(7, 3)
    assert assign_splits(docs, RATIOS, "recipe", 1) == assign_splits(docs, RATIOS, "recipe", 1)


def test_too_few_groups_is_an_error_not_silent_leakage() -> None:
    with pytest.raises(ValueError, match="too few"):
        assign_splits(_docs(recipes=2, per_recipe=5), RATIOS, "recipe", 1)
    assert assign_splits(_docs(recipes=2, per_recipe=5), RATIOS, "document", 1)


def test_template_grouping_keeps_identical_layouts_together() -> None:
    docs = [
        {"doc_id": f"d{i}", "recipe_path": "r.json", "metadata": {"layout_style": {"columns": i % 4}}} for i in range(20)
    ]
    splits = assign_splits(docs, RATIOS, "template", seed=2)
    split_of = {d: name for name, ids in splits.items() for d in ids}
    for column_count in range(4):
        assert len({split_of[f"d{i}"] for i in range(20) if i % 4 == column_count}) == 1


def test_parallel_generation_matches_sequential(tmp_path: Path) -> None:
    generate_dataset(tmp_path / "seq", count=3, variants=["random"], workers=1)
    generate_dataset(tmp_path / "par", count=3, variants=["random"], workers=2)

    for i in range(1, 4):
        name = f"synthetic_{i:06d}/truth/document.json"
        assert (tmp_path / "seq" / name).read_text() == (tmp_path / "par" / name).read_text()


def test_dataset_splits_end_to_end(tmp_path: Path) -> None:
    recipes = sorted(Path("data/recipes/canonical").glob("*.json"))
    manifest = generate_dataset(tmp_path, count=len(recipes), recipe_paths=recipes, workers=2, splits=RATIOS, split_by="recipe")

    assert {d["split"] for d in manifest["documents"]} <= set(RATIOS)
    assert json.loads((tmp_path / "splits.json").read_text())["splits"] == manifest["splits"]

    files = write_coco_splits(tmp_path)
    seen: dict[str, str] = {}
    for path in files:
        coco = json.loads(path.read_text())
        assert coco["images"]
        for image in coco["images"]:
            assert seen.setdefault(image["doc_id"], path.name) == path.name
    assert len(seen) == len(recipes)
