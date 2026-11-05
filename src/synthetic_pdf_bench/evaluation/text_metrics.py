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


def token_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein distance between two token lists (Hyyro's bit-parallel form: one big-int pass over `b`, not an n*m table)."""
    if not a or not b:
        return max(len(a), len(b))
    peq: dict[str, int] = {}
    for i, token in enumerate(a):
        peq[token] = peq.get(token, 0) | 1 << i
    mask, high = (1 << len(a)) - 1, 1 << (len(a) - 1)
    pv, mv, score = mask, 0, len(a)
    for token in b:
        eq = peq.get(token, 0)
        xv = eq | mv
        xh = (((eq & pv) + pv) ^ pv) | eq
        ph = mv | ~(xh | pv)
        mh = pv & xh
        if ph & high:
            score += 1
        elif mh & high:
            score -= 1
        ph = (ph << 1) | 1
        mh <<= 1
        pv = (mh | ~(xv | ph)) & mask
        mv = ph & xv & mask
    return score


def edit_similarity(predicted: str, expected: str) -> float:
    """1 - token-level Levenshtein distance / the longer length: 1.0 for identical text, lower for any insertion, deletion, swap or reorder."""
    a, b = _tokens(predicted), _tokens(expected)
    total = max(len(a), len(b))
    return 1.0 if total == 0 else 1 - token_distance(a, b) / total


def reading_order_score(predicted_ids: list[str], truth_ids: list[str]) -> float:
    """Share of block pairs, among blocks present in both lists, that the prediction orders like the truth (1.0 identical, about 0.5 shuffled)."""
    position = {block_id: n for n, block_id in enumerate(predicted_ids)}
    common = [block_id for block_id in truth_ids if block_id in position]
    if len(common) < 2:
        return 1.0 if common else 0.0
    pairs = [(i, j) for i in range(len(common)) for j in range(i + 1, len(common))]
    return sum(position[common[i]] < position[common[j]] for i, j in pairs) / len(pairs)
