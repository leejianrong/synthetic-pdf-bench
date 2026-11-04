import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "eval_docling_layout.py"


def _script():
    spec = importlib.util.spec_from_file_location("eval_docling_layout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docling_labels_map_onto_doclaynet_ids() -> None:
    mod = _script()
    # labels 0-10 are DocLayNet's own classes in id order (1-based)
    assert [mod.to_doclaynet(i) for i in (0, 3, 8, 9, 10)] == [1, 4, 9, 10, 11]
    assert mod.to_doclaynet(11) == 9  # Document Index is a table
    assert mod.to_doclaynet(12) == 10  # Code is text


def test_classes_without_a_doclaynet_equivalent_are_dropped_and_counted() -> None:
    mod = _script()
    for label in (13, 14, 15, 16):
        assert mod.to_doclaynet(label) is None


def test_results_are_xywh_in_page_pixels_with_dropped_counts() -> None:
    mod = _script()
    names = {9: "text", 15: "form"}
    results, dropped = mod.to_results(
        image_id=7, scores=[0.9, 0.8, 0.2], labels=[9, 15, 9], boxes=[[10, 20, 110, 70], [0, 0, 5, 5], [1, 2, 3, 4]],
        names=names, keep_score=0.5,
    )
    assert results == [
        {"image_id": 7, "category_id": 10, "bbox": [10.0, 20.0, 100.0, 50.0], "score": 0.9},
        {"image_id": 7, "category_id": 10, "bbox": [1.0, 2.0, 2.0, 2.0], "score": 0.2},
    ]
    assert dropped == {"form": 1}  # only counted at or above keep_score
