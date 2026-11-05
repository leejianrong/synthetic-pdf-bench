"""Display equations rendered with matplotlib mathtext, so size at planning time matches the drawn image."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha1
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


@lru_cache(maxsize=512)
def formula_size(latex: str, font_size: float) -> tuple[float, float]:
    """Width and height in points."""
    fig = plt.figure(dpi=72)
    box = fig.text(0, 0, f"${latex}$", fontsize=font_size).get_window_extent(fig.canvas.get_renderer())
    plt.close(fig)
    return box.width, box.height


def render_formula(latex: str, font_size: float) -> Path:
    path = Path(gettempdir()) / f"synthetic_pdf_bench_formula_{sha1(f'{latex}|{font_size}'.encode()).hexdigest()[:16]}.png"
    if not path.exists():
        width, height = formula_size(latex, font_size)
        fig = plt.figure(figsize=(width / 72, height / 72), dpi=300)
        fig.text(0, 0, f"${latex}$", fontsize=font_size)
        temp = path.with_name(f"{path.stem}.{uuid4().hex}.tmp.png")  # one name per call, so two workers never rename each other's file
        fig.savefig(temp, transparent=True)
        plt.close(fig)
        temp.replace(path)  # atomic, so parallel workers never read a half-written file
    return path
