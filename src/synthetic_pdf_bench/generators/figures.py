from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir

from PIL import Image, ImageDraw


def make_raster_figure(seed: int) -> Path:
    path = Path(gettempdir()) / f"synthetic_pdf_bench_fig_{seed}.png"
    image = Image.new("RGB", (720, 340), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([25, 35, 205, 145], outline="#2f6f73", width=5, fill="#dff3f0")
    draw.rectangle([270, 35, 450, 145], outline="#7a4c9f", width=5, fill="#efe5f8")
    draw.rectangle([515, 35, 695, 145], outline="#9a6a18", width=5, fill="#fff1cf")
    draw.line([205, 90, 270, 90], fill="#333333", width=4)
    draw.line([450, 90, 515, 90], fill="#333333", width=4)
    draw.text((68, 80), "Singapore", fill="#1a1a1a")
    draw.text((322, 80), "Malaysia", fill="#1a1a1a")
    draw.text((565, 80), "Indonesia", fill="#1a1a1a")
    draw.line([360, 150, 360, 260], fill="#555555", width=4)
    draw.ellipse([295, 245, 425, 315], outline="#2f6f73", width=5, fill="#eef8f7")
    draw.text((322, 270), "Region", fill="#1a1a1a")
    image.save(path)
    return path
