import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("layout_stats", Path(__file__).parents[1] / "scripts" / "layout_stats.py")
layout_stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(layout_stats)


def test_report_shares_and_density(tmp_path):
    coco = {"categories": [{"id": 1, "name": "text"}, {"id": 2, "name": "table"}], "images": [{"id": 1}, {"id": 2}],
            "annotations": [{"category_id": 1}, {"category_id": 1}, {"category_id": 1}, {"category_id": 2}]}
    path = tmp_path / "coco.json"
    path.write_text(json.dumps(coco))
    text = layout_stats.report({"mine": layout_stats.class_mix(path)})
    rows = {line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]] for line in text.splitlines()[2:]}
    assert rows["Text"] == ["46.1%", "75.0%"]
    assert rows["Table"] == ["3.1%", "25.0%"]
    assert rows["Footnote"][1] == "0.0%"
    assert rows["**boxes per page**"] == ["12.2", "2.0"]
