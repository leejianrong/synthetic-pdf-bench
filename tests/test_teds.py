import pytest

from synthetic_pdf_bench.evaluation.table_metrics import teds

TRUTH = [["h1", "h2"], ["a", "b"]]


def test_identical_tables_score_one() -> None:
    assert teds(TRUTH, TRUTH) == 1.0


def test_wrong_cell_text_costs_one_of_seven_nodes() -> None:
    assert teds([["h1", "h2"], ["a", "x"]], TRUTH) == pytest.approx(1 - 1 / 7)  # table + 2 rows + 4 cells


def test_missing_row_costs_a_row_and_its_cells() -> None:
    assert teds([["h1", "h2"]], TRUTH) == pytest.approx(1 - 3 / 7)


def test_partial_text_gets_partial_credit() -> None:
    assert teds([["h1", "h2"], ["a", "bx"]], TRUTH) == pytest.approx(1 - 0.5 / 7)


def test_html_spans_are_scored() -> None:
    spanned = "<table><tr><td colspan=\"2\">h</td></tr><tr><td>a</td><td>b</td></tr></table>"
    flat = "<table><tr><td>h</td><td></td></tr><tr><td>a</td><td>b</td></tr></table>"
    assert teds(spanned, spanned) == 1.0
    assert teds(flat, spanned) < 1.0
