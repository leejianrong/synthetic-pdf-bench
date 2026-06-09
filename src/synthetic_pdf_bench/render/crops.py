from __future__ import annotations

from pathlib import Path

from PIL import Image

from synthetic_pdf_bench.schema.blocks import FigureBlock


def crop_figures(figures: list[FigureBlock], page_image_paths: list[Path], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_cache: dict[int, Image.Image] = {}
    for figure in figures:
        if figure.bbox_px is None:
            continue
        if figure.page_index not in page_cache:
            page_cache[figure.page_index] = Image.open(page_image_paths[figure.page_index])
        image = page_cache[figure.page_index]
        crop = image.crop(tuple(int(value) for value in figure.bbox_px))
        output_path = output_dir / f"{figure.figure_id}.png"
        crop.save(output_path)
        figure.png_path = f"truth/figures/{output_path.name}"
