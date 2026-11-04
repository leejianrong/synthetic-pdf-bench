import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from synthetic_pdf_bench.generators.figures import _draw_timeline

CROWDED = {"events": [{"year": 1957 + n, "label": f"Independence of State {n}"} for n in range(6)]}


def test_timeline_labels_do_not_overlap() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=120)
    texts = _draw_timeline(ax, CROWDED)
    fig.tight_layout()
    renderer = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in texts]
    plt.close(fig)

    assert len(boxes) == 6
    assert not any(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1 :])
