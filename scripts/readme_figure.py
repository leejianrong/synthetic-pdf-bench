"""Regenerate docs/assets/layout-boxes.jpg: one page, clean and as a heavy scan, with layout boxes."""

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from synthetic_pdf_bench.cli.generate import generate
from synthetic_pdf_bench.export.coco import BLOCK_TYPE_TO_CATEGORY

COLORS = {"title": "#d62728", "section-header": "#1f77b4", "text": "#2ca02c", "table": "#ff7f0e",
          "picture": "#9467bd", "caption": "#8c564b", "page-header": "#7f7f7f", "page-footer": "#7f7f7f"}


def page_with_boxes(doc: Path, page: int) -> Image.Image:
    truth = json.loads((doc / "truth/document.json").read_text())
    page_truth = truth["pages"][page]
    image = Image.open(doc / page_truth["rendered_image"]["image_path"]).convert("RGB")
    draw = ImageDraw.Draw(image)
    for block in page_truth["blocks"]:
        category = BLOCK_TYPE_TO_CATEGORY[block["type"]]
        draw.rectangle(block["bbox_px"], outline=COLORS.get(category, "#000000"), width=3)
    return image.resize((image.width * 3 // 4, image.height * 3 // 4))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        generate(Path(tmp) / "clean", seed=3, variant="random")
        generate(Path(tmp) / "scan", seed=3, variant="random", degrade="heavy_scan")
        left, right = page_with_boxes(Path(tmp) / "clean", 1), page_with_boxes(Path(tmp) / "scan", 1)
        sheet = Image.new("RGB", (left.width + right.width + 20, left.height), "white")
        sheet.paste(left, (0, 0))
        sheet.paste(right, (left.width + 20, 0))
        sheet.save("docs/assets/layout-boxes.jpg", quality=80)
