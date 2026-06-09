from __future__ import annotations


def table_exact_match(predicted: list[list[str]], expected: list[list[str]]) -> bool:
    normalize = lambda matrix: [[cell.strip() for cell in row] for row in matrix]
    return normalize(predicted) == normalize(expected)
