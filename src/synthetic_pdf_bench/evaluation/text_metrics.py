from __future__ import annotations

import re


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text.lower())


def token_f1(predicted: str, expected: str) -> dict[str, float]:
    pred_tokens = _tokens(predicted)
    expected_tokens = _tokens(expected)
    if not pred_tokens and not expected_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred_tokens or not expected_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    remaining: dict[str, int] = {}
    for token in expected_tokens:
        remaining[token] = remaining.get(token, 0) + 1
    matches = 0
    for token in pred_tokens:
        if remaining.get(token, 0) > 0:
            matches += 1
            remaining[token] -= 1
    precision = matches / len(pred_tokens)
    recall = matches / len(expected_tokens)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}
