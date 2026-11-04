import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_doclaynet.py"


def _script():
    spec = importlib.util.spec_from_file_location("prepare_doclaynet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shard(path: Path, rows: int, category: str) -> None:
    png = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(png, format="PNG")
    meta = lambda i: {"coco_width": 64, "coco_height": 64, "doc_category": category, "image_id": i,
                      "original_filename": f"{category}_{i}.pdf", "page_hash": f"h{i:04d}", "page_no": i}
    table = pa.table({
        "image": [{"bytes": png.getvalue(), "path": None}] * rows,
        "bboxes": [[[4.0, 5.0, 20.0, 10.0], [-2.0, 60.0, 30.0, 30.0], [1.0, 1.0, 0.5, 9.0]]] * rows,
        "category_id": [[10, 9, 1]] * rows,
        "metadata": [meta(i) for i in range(rows)],
    })
    pq.write_table(table, path, row_group_size=4)


def test_spread_picks_evenly_spaced_distinct_shards() -> None:
    mod = _script()
    assert mod.spread(72, 12) == [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66]
    assert mod.spread(6, 6) == [0, 1, 2, 3, 4, 5]
    assert mod.spread(8, 1) == [0]


def test_converts_a_seeded_sample_to_coco(tmp_path: Path) -> None:
    mod = _script()
    shard = tmp_path / "s.parquet"
    _shard(shard, rows=10, category="manuals")

    first = mod.convert_shard(shard, tmp_path / "out", split="test", shard_index=3, quota=4, seed=7, first_id=1)
    again = mod.convert_shard(shard, tmp_path / "out2", split="test", shard_index=3, quota=4, seed=7, first_id=1)

    images, annotations = first
    assert [i["page_hash"] for i in images] == [i["page_hash"] for i in again[0]]  # same seed, same pages
    assert len(images) == 4 and len({i["page_hash"] for i in images}) == 4
    assert all((tmp_path / "out" / i["file_name"]).exists() for i in images)
    assert {i["doc_category"] for i in images} == {"manuals"}
    # the 3rd box is under 1px wide and dropped; the 2nd is clipped to the 64px page
    assert len(annotations) == 2 * len(images)
    clipped = next(a for a in annotations if a["category_id"] == 9)
    assert clipped["bbox"] == [0.0, 60.0, 28.0, 4.0]
    assert clipped["area"] == 28.0 * 4.0 and clipped["iscrowd"] == 0
    assert {a["image_id"] for a in annotations} == {i["id"] for i in images}


def test_write_dataset_emits_coco_with_the_eleven_classes(tmp_path: Path) -> None:
    mod = _script()
    shard = tmp_path / "s.parquet"
    _shard(shard, rows=6, category="patents")
    images, annotations = mod.convert_shard(shard, tmp_path / "out", split="test", shard_index=0, quota=3, seed=1, first_id=1)

    path = mod.write_coco(tmp_path / "out", "test", images, annotations)

    coco = json.loads(path.read_text())
    assert [c["name"] for c in coco["categories"]][:3] == ["caption", "footnote", "formula"]
    assert [c["id"] for c in coco["categories"]] == list(range(1, 12))
    assert len(coco["images"]) == 3
