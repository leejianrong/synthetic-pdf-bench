import random

from synthetic_pdf_bench.evaluation.text_metrics import edit_similarity, token_distance


def _reference(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        current = [i]
        for j, y in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def test_token_distance_matches_the_textbook_dynamic_programme() -> None:
    rng = random.Random(7)
    for _ in range(300):
        a = [rng.choice("abcd") for _ in range(rng.randint(0, 40))]
        b = [rng.choice("abcd") for _ in range(rng.randint(0, 40))]
        assert token_distance(a, b) == _reference(a, b)


def test_a_long_document_with_a_few_edits_scores_exactly() -> None:
    words = [f"w{n % 997}" for n in range(30000)]
    edited = words[:100] + words[110:20000] + ["x", "y"] + words[20000:]
    assert edit_similarity(" ".join(edited), " ".join(words)) == 1 - 12 / 30000
