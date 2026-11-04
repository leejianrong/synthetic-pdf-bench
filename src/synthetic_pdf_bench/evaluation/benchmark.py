"""Run a parser over every document of a generated dataset, evaluate each, and aggregate."""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from statistics import mean

from synthetic_pdf_bench.evaluation.evaluator import (
    evaluate_prediction,
    prediction_from_truth,
)

DUMMY = "dummy"


def _run_parser(parser: str, pdf: Path, truth: Path, out: Path, timeout: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if parser == DUMMY:
        prediction_from_truth(truth, out)
        return
    subprocess.run(parser.format(pdf=pdf, truth=truth, out=out), shell=True, check=True, timeout=timeout)


def _means(rows: list[dict[str, float]]) -> dict[str, float]:
    return {key: mean(row[key] for row in rows) for key in rows[0]} if rows else {}


def run_benchmark(root: Path, parser: str, output: Path, timeout: int = 600) -> dict:
    """`parser` is `dummy` (copies the truth, so every score is 1.0) or a shell command with `{pdf}`, `{truth}` and `{out}` placeholders.

    A document whose parser fails or whose output cannot be scored counts as zero on every metric and is listed under `failed`.
    """
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    scored: list[tuple[dict, dict[str, float]]] = []
    failed: list[dict] = []
    for doc in manifest["documents"]:
        folder = root / Path(doc["output_dir"]).name  # the manifest's absolute path goes stale when a dataset moves
        prediction = output / "predictions" / folder.name
        try:
            _run_parser(parser, folder / "document.pdf", folder / "truth", prediction, timeout)
            overall = {k: float(v) for k, v in evaluate_prediction(folder / "truth", prediction)["overall"].items()}
        except Exception as err:  # noqa: BLE001 - any parser or scoring failure is a result, not a crash
            failed.append({"doc_id": doc["doc_id"], "error": f"{type(err).__name__}: {err}"[:300]})
            continue
        scored.append((doc, overall))
    keys = list(scored[0][1]) if scored else []
    rows = [(doc, overall) for doc, overall in scored] + [(doc, dict.fromkeys(keys, 0.0)) for doc in manifest["documents"] if doc["doc_id"] in {f["doc_id"] for f in failed}]
    groups: dict[str, dict[str, list[dict[str, float]]]] = {"variant": defaultdict(list), "split": defaultdict(list)}
    for doc, overall in rows:
        groups["variant"][doc["recipe_variant"]].append(overall)
        if doc.get("split"):
            groups["split"][doc["split"]].append(overall)
    report = {
        "parser": parser,
        "documents": len(manifest["documents"]),
        "failed": failed,
        "mean": _means([overall for _, overall in rows]),
        "by_variant": {name: {"documents": len(r), "mean": _means(r)} for name, r in sorted(groups["variant"].items())},
        "by_split": {name: {"documents": len(r), "mean": _means(r)} for name, r in sorted(groups["split"].items())},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
