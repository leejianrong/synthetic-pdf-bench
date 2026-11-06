"""Pages laid out on the box layouts of real DocLayNet pages, filled with generated content.

A bank page is one record of `scripts/doclaynet_survey.py` (boxes as page fractions with class, text length, type height and font). Each box
becomes one block in the same place and of the same class, holding content that fits it: text wrapped to the box, a table gridded to the box, a
picture, a formula. Composition, box sizes, positions, page size and overlaps therefore match real pages by construction; only the content and
the look are synthetic. Use the bank of the train split only (`load_layout_bank` refuses other splits by default).
"""

from __future__ import annotations

import gzip
import json
import random
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics

from synthetic_pdf_bench.generators.formulas import formula_size
from synthetic_pdf_bench.generators.recipes import DocumentRecipe, load_recipe
from synthetic_pdf_bench.generators.tables import table_to_html, table_to_markdown
from synthetic_pdf_bench.layout.flow_layout import FlowLayoutPlanner
from synthetic_pdf_bench.layout.scene import SceneGraph
from synthetic_pdf_bench.layout.text_lines import ASCENT, DESCENT, text_lines
from synthetic_pdf_bench.render.fonts import font_for_text
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock

BLOCK_TYPE = {"text": "paragraph", "list-item": "list_item", "section-header": "heading", "title": "title", "caption": "caption",
              "footnote": "footnote", "formula": "formula", "page-header": "header", "page-footer": "footer", "picture": "figure", "table": "table"}
FURNITURE = {"header", "footer", "page_number"}
MIN_SIDE = 4.0  # boxes smaller than this (points) are skipped
FORMULAS = [r"E = mc^2", r"x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}", r"\sum_{i=1}^{n} x_i = \frac{n(n+1)}{2}", r"p(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
            r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}", r"a^2 + b^2 = c^2", r"\alpha_t = \beta_t + \gamma", r"\nabla \cdot \mathbf{E} = \frac{\rho}{\epsilon_0}",
            r"y = \alpha + \beta x + \epsilon", r"\lim_{n \to \infty} \left(1 + \frac{1}{n}\right)^n = e"]


def load_layout_bank(source: Path, split: str = "train") -> dict[str, list[dict]]:
    """Bank pages grouped by source document, in page order. Only `split` pages are kept, so validation and test layouts never train anything."""
    files = sorted(source.glob("*.jsonl.gz")) if source.is_dir() else [source]
    bank: dict[str, list[dict]] = defaultdict(list)
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                page = json.loads(line)
                if page["split"] == split and page["boxes"]:  # unannotated pages would replay as blank pages
                    bank[page["doc"]].append(page)
    for pages in bank.values():
        pages.sort(key=lambda p: p["page_no"])
    return dict(bank)


def family_for(font: str | None) -> str:
    """The built-in family closest to a real font name."""
    low = (font or "").lower()
    if re.search(r"courier|mono|typewriter|consolas|cmtt", low):
        return "Courier"
    if re.search(r"helvetica|arial|sans|calibri|verdana|myriad|tahoma|segoe|frutiger|univers|lato|roboto|gothic", low):
        return "Helvetica"
    if re.search(r"times|serif|roman|cmr|cmbx|nimbus|garamond|palatino|century|book|georgia|minion|cambria", low):
        return "Times"
    return "Helvetica"


def _document_family(pages: list[dict]) -> str:
    fonts = Counter(family_for(box[8]) for page in pages for box in page["boxes"] if box[8])
    return fonts.most_common(1)[0][0] if fonts else "Helvetica"


def _line_box(font_size: float) -> float:
    return (ASCENT + DESCENT) * font_size


def _fit_word(word: str, font: str, size: float, width: float) -> str:
    while len(word) > 1 and pdfmetrics.stringWidth(word, font, size) > width:
        word = word[:-1]
    return word


class ReplayPlanner:
    def __init__(self, recipe: DocumentRecipe, pages: list[dict], seed: int, dpi: int = 144) -> None:
        self.recipe, self.pages, self.seed, self.dpi = recipe, pages, seed, dpi
        self.rng = random.Random(f"{seed}-replay")
        words = " ".join(b.text for s in recipe.sections for b in s.blocks if b.type == "paragraph").split()
        self.words = [w for w in words if w.isascii()] or ["lorem", "ipsum"]
        self.family = _document_family(pages)
        self.scene = SceneGraph(doc_id=recipe.doc_id, seed=seed, dpi=dpi)
        self.block_counter = self.reading_order = self.figure_counter = self.table_counter = 0
        self.table_helper = FlowLayoutPlanner(seed=seed, dpi=dpi)

    def build_scene(self) -> SceneGraph:
        scene = self.scene
        scene.language_profile = self.recipe.language_profile
        first = self.pages[0]
        scene.metadata = {**self.recipe.metadata, "recipe_variant": "replay", "variant_seed": self.seed, "base_doc_id": self.recipe.metadata.get("base_doc_id", self.recipe.doc_id),
                          "layout_style": {"font_family": self.family},
                          "layout_source": {"doc": first["doc"], "category": first["category"], "pages": [p["page_no"] for p in self.pages]}}
        for source in self.pages:
            page = scene.add_page(width_pt=source["w_pt"], height_pt=source["h_pt"])
            boxes = sorted(source["boxes"], key=lambda b: (round(b[2], 3), b[1]))
            for rank, box in enumerate(boxes):
                self._add_box(page.page_index, source, box, rank)
        return scene

    def _text(self, chars: int, font: str, size: float, width: float) -> str:
        """About `chars` characters of running text, cut at a word, every word short enough to fit the width."""
        start, out = self.rng.randrange(len(self.words)), []
        total = 0
        for k in range(len(self.words)):
            word = _fit_word(self.words[(start + k) % len(self.words)], font, size, width)
            out.append(word)
            total += len(word) + 1
            if total >= max(chars, 1):
                break
        return " ".join(out)

    def _block_id(self) -> str:
        self.block_counter += 1
        return f"b{self.block_counter:06d}"

    def _add_box(self, page_index: int, source: dict, box: list, rank: int) -> None:
        cls, x, y, w, h, _cells, chars, cell_h, _font = box
        width_pt, height_pt = source["w_pt"], source["h_pt"]
        bbox = [max(x, 0.0) * width_pt, max(1 - y - h, 0.0) * height_pt, min(x + w, 1.0) * width_pt, min(1 - y, 1.0) * height_pt]
        if bbox[2] - bbox[0] < MIN_SIDE or bbox[3] - bbox[1] < MIN_SIDE:
            return
        kind = BLOCK_TYPE[cls]
        if kind == "table":
            self._add_table(page_index, bbox, cell_h)
        elif kind == "figure":
            self._add_figure(page_index, bbox, rank)
        elif kind == "formula":
            self._add_formula(page_index, bbox, rank)
        else:
            self._add_text(page_index, source, kind, bbox, chars, cell_h, rank)

    def _order(self, kind: str, page_index: int, rank: int) -> tuple[int, bool]:
        if kind == "header":
            return -1000 + page_index, False
        if kind in {"footer", "page_number"}:
            return 100000 + page_index, False
        self.reading_order += 1
        return self.reading_order, True

    def _add_text(self, page_index: int, source: dict, kind: str, bbox: list[float], chars: int, cell_h: float | None, rank: int) -> None:
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        size = min(max((cell_h or 9.0) / _line_box(1.0), 4.0), 28.0, height / 1.25)  # a line box is 1.02 x the size and sits 0.2 x below the baseline
        bold = kind in {"title", "heading"}
        font = font_for_text("x", bold=bold, family=self.family)
        hang = size * 1.8 if kind == "list_item" and width > 6 * size else 0.0
        if kind == "footer" and chars <= 4:
            kind = "page_number"
            text = str(page_index + 1)[: max(chars, 1)]
        else:  # a one-line box keeps its real length; a taller box is as full of text as real ones are
            lines_fit = int(height / (size * 1.2))
            wanted = chars if lines_fit <= 1 else int(lines_fit * (width - hang) / (0.47 * size))
            text = self._text(wanted, font, size, width - hang)
        block = Block(block_id=self._block_id(), type=kind, page_index=page_index, reading_order=0, bbox_pt=bbox, text=text)
        block.metadata = {"font_size": size, "line_height": round(size * 1.2, 2), "font_family": self.family, "role": kind}
        if hang:
            block.metadata |= {"marker": "•", "hang": hang}
        block.lines = [line for line in text_lines(block, bold=bold, dpi=self.dpi, page_height_pt=source["h_pt"]) if line.bbox_pt[1] >= bbox[1] - 0.5]
        if not block.lines:
            return
        drawn = " ".join(line.text for line in block.lines)
        block.text = drawn.replace("• ", "", 1) if hang else drawn
        order, in_markdown = self._order(kind, page_index, rank)
        block.reading_order, block.include_in_markdown = order, in_markdown
        block.markdown = {"heading": f"## {block.text}", "title": f"# {block.text}", "list_item": f"- {block.text}", "caption": f"*{block.text.rstrip('.')}.*"}.get(kind, block.text)
        self.scene.add_block(block)

    def _add_figure(self, page_index: int, bbox: list[float], rank: int) -> None:
        self.figure_counter += 1
        figure_id = f"fig_{self.figure_counter:03d}"
        ref = f"![Figure {self.figure_counter}](figures/{figure_id}.png)"
        order, _ = self._order("figure", page_index, rank)
        self.scene.add_block(FigureBlock(block_id=self._block_id(), page_index=page_index, reading_order=order, bbox_pt=bbox, figure_id=figure_id, kind="photo",
                                         source_type="raster", png_path=f"truth/figures/{figure_id}.png", markdown_ref=ref, markdown=ref, metadata={"title": "", "data": {}}))

    def _add_formula(self, page_index: int, bbox: list[float], rank: int) -> None:
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        latex = min(FORMULAS, key=lambda f: abs(formula_size(f, 12)[0] / formula_size(f, 12)[1] - width / height))
        size = min(max(12 * height / formula_size(latex, 12)[1], 6.0), 40.0)
        order, _ = self._order("formula", page_index, rank)
        self.scene.add_block(Block(block_id=self._block_id(), type="formula", page_index=page_index, reading_order=order, bbox_pt=bbox, text=latex,
                                   markdown=f"$${latex}$$", metadata={"font_size": size, "image_box": list(bbox), "number": None}))

    def _add_table(self, page_index: int, bbox: list[float], cell_h: float | None) -> None:
        self.table_counter += 1
        table_id = f"tbl_{self.table_counter:03d}"
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 4, 3
        size = min(max((cell_h or 8.0) / _line_box(1.0), 4.0), 12.0)
        rows = int(height / (size * 1.2 + 2 * pad_y))
        if rows < 2:  # a small table: shrink the type until a header and a body row fit, if they can
            size = 4.0
            rows = max(1, int(height / (size * 1.2 + 2 * pad_y)))
        columns = min(max(round(width / 70), 2), 8)
        font, bold = font_for_text("x", family=self.family), font_for_text("x", bold=True, family=self.family)
        col_width = width / columns
        matrix = [[self._cell(r == 0, bold if r == 0 else font, size, col_width - 2 * pad_x) for _ in range(columns)] for r in range(rows)]
        row_heights, col_widths = [height / rows] * rows, [col_width] * columns
        wrapped = [[[text] for text in row] for row in matrix]
        cells = self.table_helper._table_cells(table_id, matrix, page_index, bbox, row_heights, col_widths, wrapped, [])
        for cell in cells:  # sums of equal widths can overshoot the table edge by a rounding error, which the quality check rejects
            cell.bbox_pt = [max(cell.bbox_pt[0], bbox[0]), max(cell.bbox_pt[1], bbox[1]), min(cell.bbox_pt[2], bbox[2]), min(cell.bbox_pt[3], bbox[3])]
        order, _ = self._order("table", page_index, 0)
        self.scene.add_block(TableBlock(block_id=self._block_id(), page_index=page_index, reading_order=order, bbox_pt=bbox, table_id=table_id, matrix=matrix,
                                        markdown=table_to_markdown(matrix), html=table_to_html(matrix, []), cells=cells,
                                        metadata={"title": "", "caption": "", "merged_cells": [], "parent_table_id": table_id, "table_segment_index": 0,
                                                  "body_rows_remaining": 0, "font_size": size, "line_height": round(size * 1.2, 2), "font_family": self.family,
                                                  "cell_padding": [pad_x, pad_y]}))

    def _cell(self, header: bool, font: str, size: float, width: float) -> str:
        if header or self.rng.random() < 0.4:
            text = self.words[self.rng.randrange(len(self.words))]
            text = text.capitalize() if header else text
        else:
            text = f"{self.rng.randint(1, 99999):,}"
        return _fit_word(text, font, size, max(width, 4.0))


@lru_cache(maxsize=2)
def _bank(path: str) -> dict[str, list[dict]]:
    return load_layout_bank(Path(path))


def build_replay_scene_from_path(recipe_path: Path, seed: int, dpi: int, layout_bank: Path) -> SceneGraph:
    """One document: the text of the recipe on the layouts of one real train document chosen by `seed`."""
    base = load_recipe(recipe_path)
    recipe = base.model_copy(deep=True)
    recipe.doc_id = f"{base.doc_id}_replay_{seed:06d}"
    recipe.metadata = {**recipe.metadata, "base_doc_id": base.doc_id}
    return build_replay_scene(recipe, sample_document(_bank(str(layout_bank)), seed), seed, dpi)


def build_replay_scene(recipe: DocumentRecipe, pages: list[dict], seed: int, dpi: int = 144) -> SceneGraph:
    return ReplayPlanner(recipe, pages, seed, dpi).build_scene()


def sample_document(bank: dict[str, list[dict]], seed: int, max_pages: int = 12) -> list[dict]:
    """A real document's layouts chosen by page count (so every page is equally likely), at most `max_pages` of them in page order."""
    rng = random.Random(f"{seed}-bank")
    docs = sorted(bank)
    doc = rng.choices(docs, weights=[len(bank[d]) for d in docs])[0]
    pages = bank[doc]
    return sorted(rng.sample(pages, min(max_pages, len(pages))), key=lambda p: p["page_no"])
