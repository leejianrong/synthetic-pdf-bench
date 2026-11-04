from synthetic_pdf_bench.evaluation.normalize_markdown import normalize_markdown
from synthetic_pdf_bench.evaluation.table_metrics import table_exact_match
from synthetic_pdf_bench.evaluation.text_metrics import (
    edit_similarity,
    reading_order_score,
    token_f1,
)


def test_normalize_markdown() -> None:
    assert normalize_markdown("A   B\n\n\nC\n") == "A B\n\nC"


def test_token_f1() -> None:
    scores = token_f1("Singapore and 简体中文", "Singapore 简体中文")
    assert scores["precision"] < 1
    assert scores["recall"] == 1


def test_table_exact_match() -> None:
    assert table_exact_match([["A", " B "]], [["A", "B"]])
    assert not table_exact_match([["A", "C"]], [["A", "B"]])


def test_edit_similarity() -> None:
    assert edit_similarity("a b c d", "a b c d") == 1.0
    assert edit_similarity("a b c d", "a b x d") == 0.75
    assert edit_similarity("a b", "") == 0.0
    assert edit_similarity("", "") == 1.0
    assert edit_similarity("d c b a", "a b c d") < edit_similarity("a b c d e", "a b c d")  # a reorder costs more than one insertion


def test_reading_order_score() -> None:
    truth = [f"b{n}" for n in range(8)]
    assert reading_order_score(truth, truth) == 1.0
    assert reading_order_score(truth[::-1], truth) == 0.0
    shuffled = ["b3", "b0", "b6", "b1", "b7", "b2", "b5", "b4"]
    assert 0.0 < reading_order_score(shuffled, truth) < 1.0
    assert reading_order_score(truth[:4] + ["extra"], truth) == 1.0  # unmatched ids are ignored; id matching is the evaluator's job
    assert reading_order_score([], truth) == 0.0
