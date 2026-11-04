"""Scan-style degradation of rendered pages, with matching ``bbox_px`` transforms.

Only ``bbox_px`` follows the degraded image. ``bbox_pt`` and ``bbox_norm`` keep describing
the digital PDF, and figure crops stay clean.
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.schema.blocks import TableBlock
from synthetic_pdf_bench.schema.truth import PageTruth


@dataclass(frozen=True)
class Degradation:
    """Upper bounds; each page samples its own values below them."""

    max_skew_deg: float = 0.0
    max_shift_px: int = 0
    max_blur_px: float = 0.0
    max_noise_sigma: float = 0.0
    min_contrast: float = 1.0
    jpeg_quality: int | None = None
    grayscale: bool = False


PROFILES = {
    "light_scan": Degradation(0.6, 6, 0.5, 4, 0.9, 80, True),
    "heavy_scan": Degradation(2.5, 20, 1.2, 14, 0.7, 45, True),
}


def degrade_image(image: Image.Image, profile: Degradation, rng: random.Random) -> tuple[Image.Image, dict]:
    """Skew/shift, then contrast, blur, noise and JPEG artifacts. Same-size output."""
    angle = rng.uniform(-profile.max_skew_deg, profile.max_skew_deg)
    shift = (rng.randint(-profile.max_shift_px, profile.max_shift_px), rng.randint(-profile.max_shift_px, profile.max_shift_px))
    contrast = rng.uniform(profile.min_contrast, 1.0)
    blur = rng.uniform(0, profile.max_blur_px)
    sigma = rng.uniform(profile.max_noise_sigma / 2, profile.max_noise_sigma)
    noise_rng = np.random.default_rng(rng.getrandbits(32))

    image = image.convert("L" if profile.grayscale else "RGB")
    white = 255 if profile.grayscale else (255, 255, 255)
    image = image.rotate(angle, resample=Image.Resampling.BICUBIC, translate=shift, fillcolor=white)
    image = ImageEnhance.Contrast(image).enhance(contrast)
    if blur > 0:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    if sigma > 0:
        noisy = np.asarray(image, dtype=np.float32) + noise_rng.normal(0, sigma, np.asarray(image).shape)
        image = Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8))
    if profile.jpeg_quality is not None:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=profile.jpeg_quality)
        image = Image.open(buffer)
        image.load()
    params = {"angle_deg": angle, "shift_px": list(shift), "contrast": contrast, "blur_px": blur, "noise_sigma": sigma}
    return image, params


def transform_bbox(bbox: list[float], angle_deg: float, shift: tuple[int, int], size: tuple[int, int]) -> list[float]:
    """Axis-aligned box of the corners after PIL's rotate-about-center-then-translate, clipped to the image."""
    width, height = size
    cx, cy = width / 2, height / 2
    cos, sin = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    x0, y0, x1, y1 = bbox
    xs, ys = [], []
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        dx, dy = x - cx, y - cy
        xs.append(cx + dx * cos + dy * sin + shift[0])
        ys.append(cy - dx * sin + dy * cos + shift[1])
    return [max(0.0, min(xs)), max(0.0, min(ys)), min(float(width), max(xs)), min(float(height), max(ys))]


def degrade_pages(scene: SceneGraph, page_paths: list[Path], profile_name: str, seed: int) -> None:
    """Overwrite the page PNGs with degraded versions and move every ``bbox_px`` to match."""
    profile = PROFILES[profile_name]
    for page, path in zip(scene.pages, page_paths, strict=True):
        with Image.open(path) as source:
            degraded, params = degrade_image(source, profile, random.Random(f"{seed}:{page.page_index}"))
        degraded.save(path)
        move = (params["angle_deg"], tuple(params["shift_px"]), degraded.size)
        for block in page.blocks:
            block.bbox_px = transform_bbox(block.bbox_px, *move)
            for line in block.lines:
                line.bbox_px = transform_bbox(line.bbox_px, *move)
                for word in line.words:
                    word.bbox_px = transform_bbox(word.bbox_px, *move)
            if isinstance(block, TableBlock):
                for cell in block.cells:
                    cell.bbox_px = transform_bbox(cell.bbox_px, *move)
        assert page.rendered_image is not None
        page.rendered_image.degradation = {"profile": profile_name, **params}


def write_scan_pdf(page_paths: list[Path], pages: list[PageTruth], output_pdf: Path) -> None:
    """Image-only PDF, one page image per page, at the original page size."""
    with fitz.open() as doc:
        for page, path in zip(pages, page_paths, strict=True):
            pdf_page = doc.new_page(width=page.width_pt, height=page.height_pt)
            pdf_page.insert_image(pdf_page.rect, filename=str(path))
        doc.save(output_pdf)
