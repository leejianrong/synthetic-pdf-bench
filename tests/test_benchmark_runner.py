import json
import sys
from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.evaluation.benchmark import run_benchmark

RECIPE = Path("data/recipes/canonical/visual_benchmark_v1.json")


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "ds"
    generate_dataset(root, count=10, recipe_paths=[RECIPE], variants=["standard", "compact"], splits={"train": 0.5, "val": 0.5}, split_by="document")
    return root


def test_dummy_parser_scores_one_everywhere(tmp_path: Path) -> None:
    report = run_benchmark(_dataset(tmp_path), "dummy", tmp_path / "out")

    assert report["documents"] == 10 and report["failed"] == []
    assert all(v == 1.0 for v in report["mean"].values()) and "reading_order" in report["mean"]
    assert set(report["by_variant"]) == {"standard", "compact"} and set(report["by_split"]) == {"train", "val"}
    assert sum(g["documents"] for g in report["by_variant"].values()) == 10
    assert json.loads((tmp_path / "out" / "benchmark.json").read_text())["mean"] == report["mean"]


def test_failing_parser_counts_as_zero(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    cli = f"{sys.executable} -c 'from synthetic_pdf_bench.cli.generate import main; main()' dummy-parse --truth {{truth}} --prediction {{out}}"
    refuse_first = f"{sys.executable} -c 'import sys; sys.exit(\"000001\" in sys.argv[1])' {{pdf}}"
    report = run_benchmark(root, f"{refuse_first} && {cli}", tmp_path / "out")

    assert [f["doc_id"] for f in report["failed"]] == [json.loads((root / "manifest.json").read_text())["documents"][0]["doc_id"]]
    assert report["mean"]["markdown_token_f1"] == 0.9
    assert sum(g["documents"] for g in report["by_variant"].values()) == 10
