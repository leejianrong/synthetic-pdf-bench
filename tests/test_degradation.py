import json
import random
from pathlib import Path

import fitz
import numpy as np
import pytest
from PIL import Image

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.degrade import PROFILES, degrade_image, transform_bbox
from synthetic_pdf_bench.export.coco import export_coco
from synthetic_pdf_bench.schema.truth import DocumentTruth


@pytest.mark.parametrize(("angle", "shift"), [(0.0, (0, 0)), (2.5, (0, 0)), (-2.5, (12, -7)), (1.0, (-20, 20))])
def test_transformed_bbox_matches_where_the_pixels_land(angle: float, shift: tuple[int, int]) -> None:
    size = (600, 800)
    box = [150, 200, 450, 260]
    image = Image.new("L", size, 255)
    image.paste(0, tuple(box))
    rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, translate=shift, fillcolor=255)

    ys, xs = np.nonzero(np.asarray(rotated) < 128)
    measured = [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]

    assert transform_bbox(box, angle, shift, size) == pytest.approx(measured, abs=2.5)


def test_degradation_is_deterministic_per_seed() -> None:
    image = Image.new("RGB", (200, 300), "white")
    profile = PROFILES["heavy_scan"]
    a, params_a = degrade_image(image, profile, random.Random("7:0"))
    b, params_b = degrade_image(image, profile, random.Random("7:0"))
    c, _ = degrade_image(image, profile, random.Random("8:0"))

    assert params_a == params_b
    assert np.array_equal(np.asarray(a), np.asarray(b))
    assert not np.array_equal(np.asarray(a), np.asarray(c))


def test_scan_document_is_image_only_with_moved_pixel_boxes_and_unchanged_pdf_boxes(tmp_path: Path) -> None:
    generate(tmp_path / "clean", seed=3)
    generate(tmp_path / "scan", seed=3, degrade="heavy_scan")
    clean = DocumentTruth.model_validate_json((tmp_path / "clean/truth/document.json").read_text())
    scan = DocumentTruth.model_validate_json((tmp_path / "scan/truth/document.json").read_text())

    with fitz.open(tmp_path / "scan/document.pdf") as pdf:
        assert all(not page.get_text().strip() and page.get_images() for page in pdf)
    with fitz.open(tmp_path / "scan/document_clean.pdf") as pdf:
        assert pdf[0].get_text().strip()

    assert [b.bbox_pt for b in scan.blocks] == [b.bbox_pt for b in clean.blocks]
    assert [b.bbox_px for b in scan.blocks] != [b.bbox_px for b in clean.blocks]
    assert all(p.rendered_image.degradation["profile"] == "heavy_scan" for p in scan.pages)

    coco = export_coco(tmp_path / "scan")
    sizes = {i["id"]: (i["width"], i["height"]) for i in coco["images"]}
    for ann in coco["annotations"]:
        w, h = sizes[ann["image_id"]]
        x, y, bw, bh = ann["bbox"]
        assert 0 <= x and 0 <= y and x + bw <= w + 1e-6 and y + bh <= h + 1e-6
        assert bw > 0 and bh > 0


def test_regenerating_clean_removes_the_stale_clean_pdf(tmp_path: Path) -> None:
    generate(tmp_path / "doc", seed=3, degrade="light_scan")
    assert (tmp_path / "doc/document_clean.pdf").exists()
    generate(tmp_path / "doc", seed=3)
    assert not (tmp_path / "doc/document_clean.pdf").exists()
    assert json.loads((tmp_path / "doc/truth/manifest.json").read_text())["degradation"] == "none"
