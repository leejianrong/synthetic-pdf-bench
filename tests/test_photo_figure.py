from PIL import Image

from synthetic_pdf_bench.generators.figures import make_photo_figure


def test_photo_figure_is_full_colour_and_varies_by_figure() -> None:
    first = Image.open(make_photo_figure(1, "fig-1")).convert("RGB")
    again = Image.open(make_photo_figure(1, "fig-1")).convert("RGB")
    other = Image.open(make_photo_figure(1, "fig-2")).convert("RGB")

    assert first.tobytes() == again.tobytes()  # deterministic
    assert first.tobytes() != other.tobytes()
    assert len(first.getcolors(maxcolors=1 << 20)) > 5000  # a photo has continuous tone, the flat diagram has under ten colours
    white = sum(1 for px in first.getdata() if min(px) > 245)
    assert white < 0.05 * first.width * first.height  # covers its box rather than sitting on white
