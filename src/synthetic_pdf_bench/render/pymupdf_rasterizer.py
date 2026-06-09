from __future__ import annotations

from pathlib import Path

import fitz


def rasterize_pdf(pdf_path: Path, output_dir: Path, dpi: int = 144) -> list[tuple[Path, int, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[Path, int, int]] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            path = output_dir / f"page_{page_index + 1:03d}.png"
            pix.save(path)
            rendered.append((path, pix.width, pix.height))
    return rendered
