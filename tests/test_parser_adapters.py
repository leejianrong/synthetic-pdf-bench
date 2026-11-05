import subprocess
import sys
from pathlib import Path

import pytest

from synthetic_pdf_bench.cli.generate import generate_dataset
from synthetic_pdf_bench.evaluation.benchmark import run_benchmark

RECIPES = sorted(Path("data/recipes/canonical").glob("*.json"))


@pytest.mark.parametrize("script", ["pymupdf_text", "pypdf_text"])
def test_text_baselines_score_between_zero_and_one(tmp_path: Path, script: str) -> None:
    pytest.importorskip("pypdf")
    generate_dataset(tmp_path / "ds", count=2, recipe_paths=RECIPES[:2], variants=["standard"])
    command = f"{sys.executable} scripts/parsers/{script}.py {{pdf}} {{out}}"

    report = run_benchmark(tmp_path / "ds", command, tmp_path / "out")

    assert not report["failed"]
    assert 0.3 < report["mean"]["markdown_token_f1"] < 1.0  # extracts the words, but not the Markdown structure
