from collections import Counter

from synthetic_pdf_bench.layout.flow_layout import random_style


def test_random_styles_favour_realistic_fonts_and_often_use_two_columns() -> None:
    styles = [random_style(seed) for seed in range(400)]
    fonts = Counter(s.font_family for s in styles)
    columns = sum(s.columns == 2 for s in styles) / len(styles)

    assert fonts["Courier"] < 0.1 * len(styles)  # monospaced body text is rare in DocLayNet
    assert fonts["Times"] > 0.15 * len(styles) and fonts["Helvetica"] > 0.15 * len(styles)  # with the LaTeX, DejaVu and STIX families sharing the rest
    assert columns >= 0.45  # real pages are often multi-column; real text blocks are half the synthetic width
