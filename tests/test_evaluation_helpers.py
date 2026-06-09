from synthetic_pdf_bench.evaluation.normalize_markdown import normalize_markdown
from synthetic_pdf_bench.evaluation.table_metrics import table_exact_match
from synthetic_pdf_bench.evaluation.text_metrics import token_f1


def test_normalize_markdown() -> None:
    assert normalize_markdown("A   B\n\n\nC\n") == "A B\n\nC"


def test_token_f1() -> None:
    scores = token_f1("Singapore and 简体中文", "Singapore 简体中文")
    assert scores["precision"] < 1
    assert scores["recall"] == 1


def test_table_exact_match() -> None:
    assert table_exact_match([["A", " B "]], [["A", "B"]])
    assert not table_exact_match([["A", "C"]], [["A", "B"]])
