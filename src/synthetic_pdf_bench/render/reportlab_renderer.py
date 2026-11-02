from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from synthetic_pdf_bench.generators.figures import (
    make_matplotlib_figure,
    make_raster_figure,
)
from synthetic_pdf_bench.render.fonts import contains_cjk, font_for_text, register_fonts
from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock
from synthetic_pdf_bench.schema.truth import PageTruth


class ReportLabRenderer:
    def __init__(self, seed: int = 123) -> None:
        self.seed = seed
        register_fonts()

    def render(self, pages: list[PageTruth], output_pdf: Path) -> None:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        canvas = Canvas(str(output_pdf), pagesize=(pages[0].width_pt, pages[0].height_pt))
        for page in pages:
            canvas.setPageSize((page.width_pt, page.height_pt))
            for block in sorted(page.blocks, key=lambda item: item.reading_order):
                self._draw_block(canvas, block)
            canvas.showPage()
        canvas.save()

    def _draw_block(self, canvas: Canvas, block: Block | TableBlock | FigureBlock) -> None:
        if isinstance(block, TableBlock):
            self._draw_table(canvas, block)
        elif isinstance(block, FigureBlock):
            self._draw_figure(canvas, block)
        elif block.type == "title":
            self._draw_text(canvas, block, font_size=20, bold=True)
        elif block.type == "heading":
            self._draw_text(canvas, block, font_size=14, bold=True)
        elif block.type in {"footnote", "reference", "caption"} or block.type in {"footer", "page_number", "header"}:
            self._draw_text(canvas, block, font_size=8)
        else:
            self._draw_text(canvas, block, font_size=10)

    def _draw_text(self, canvas: Canvas, block: Block, font_size: int, bold: bool = False) -> None:
        x0, y0, x1, y1 = block.bbox_pt
        canvas.setFillColor(colors.black)
        text = block.markdown if block.type == "list" and block.markdown else block.text or block.markdown
        font_name = font_for_text(text, bold=bold)
        canvas.setFont(font_name, font_size)
        lines = self._wrap_text(canvas, text, font_name, font_size, x1 - x0)
        y = y1 - font_size
        for line in lines:
            if y < y0:
                break
            canvas.drawString(x0, y, line)
            y -= font_size * 1.25

    def _draw_table(self, canvas: Canvas, block: TableBlock) -> None:
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.75)
        for cell in block.cells:
            x0, y0, x1, y1 = cell.bbox_pt
            if cell.is_header:
                canvas.setFillColor(colors.HexColor("#eef2f4"))
                canvas.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
            canvas.setFillColor(colors.black)
            canvas.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)
            font_name = font_for_text(cell.text, bold=cell.is_header)
            canvas.setFont(font_name, 7)
            lines = self._wrap_text(canvas, cell.text, font_name, 7, x1 - x0 - 8)
            y = y1 - 10
            for line in lines[:2]:
                if y <= y0 + 3:
                    break
                canvas.drawString(x0 + 4, y, line)
                y -= 8

    def _draw_figure(self, canvas: Canvas, block: FigureBlock) -> None:
        x0, y0, x1, y1 = block.bbox_pt
        if block.source_type == "raster":
            data = block.metadata.get("data", {})
            if data.get("backend") == "matplotlib" or block.kind in {
                "bar_chart",
                "line_chart",
                "stacked_bar",
                "timeline",
                "scatter_plot",
                "heatmap",
            }:
                image_path = make_matplotlib_figure(block.kind, data, self.seed, block.figure_id)
            else:
                image_path = make_raster_figure(self.seed)
            canvas.drawImage(ImageReader(str(image_path)), x0, y0, x1 - x0, y1 - y0)
            return
        if block.kind == "timeline":
            self._draw_timeline(canvas, block)
        elif block.kind == "comparison_chart":
            self._draw_comparison_chart(canvas, block)
        elif block.kind == "flow_diagram":
            self._draw_flow_diagram(canvas, block)
        elif block.kind == "regional_map_placeholder":
            self._draw_regional_map_placeholder(canvas, block)
        else:
            self._draw_vector_placeholder(canvas, block)

    def _wrap_text(self, canvas: Canvas, text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
        tokens = self._wrap_tokens(text)
        lines: list[str] = []
        current = ""
        for token in tokens:
            candidate = token if not current else current + token
            if canvas.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current.strip())
            current = token.lstrip()
        if current:
            lines.append(current.strip())
        return lines or [""]

    def _wrap_tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        current = ""
        for char in text:
            if contains_cjk(char):
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
            elif char.isspace():
                current += char
                tokens.append(current)
                current = ""
            else:
                current += char
        if current:
            tokens.append(current)
        return tokens

    def _draw_figure_frame(self, canvas: Canvas, block: FigureBlock, title: str) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = block.bbox_pt
        canvas.setStrokeColor(colors.HexColor("#5d6970"))
        canvas.setFillColor(colors.HexColor("#f7f9f9"))
        canvas.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=1)
        canvas.setFillColor(colors.black)
        canvas.setFont(font_for_text(title, bold=True), 8)
        canvas.drawString(x0 + 8, y1 - 13, title[:90])
        return x0 + 14, y0 + 14, x1 - 14, y1 - 24

    def _draw_timeline(self, canvas: Canvas, block: FigureBlock) -> None:
        data = block.metadata.get("data", {})
        title = block.metadata.get("title", "Timeline")
        x0, y0, x1, y1 = self._draw_figure_frame(canvas, block, title)
        scale = data.get("scale", {})
        start_year = scale.get("start_year", 1900)
        end_year = scale.get("end_year", 2025)
        lanes = data.get("lanes", [])
        lane_gap = (y1 - y0) / max(1, len(lanes))
        canvas.setFont("Helvetica", 6)
        for lane_idx, lane in enumerate(lanes):
            y = y1 - lane_gap * (lane_idx + 0.5)
            canvas.setStrokeColor(colors.HexColor("#8c969b"))
            canvas.line(x0 + 70, y, x1 - 10, y)
            canvas.setFillColor(colors.black)
            canvas.drawString(x0, y - 3, lane.get("label", "Lane"))
            for event in lane.get("events", []):
                year = event.get("year", start_year)
                pos = (year - start_year) / max(1, end_year - start_year)
                ex = x0 + 70 + pos * (x1 - x0 - 80)
                canvas.setFillColor(colors.HexColor("#2f6f73"))
                canvas.circle(ex, y, 2.5, stroke=0, fill=1)
                canvas.setFillColor(colors.black)
                canvas.drawString(ex + 3, y + 4, str(event.get("short_label", year))[:18])

    def _draw_comparison_chart(self, canvas: Canvas, block: FigureBlock) -> None:
        data = block.metadata.get("data", {})
        title = block.metadata.get("title", "Comparison")
        x0, y0, x1, y1 = self._draw_figure_frame(canvas, block, title)
        labels = data.get("y_axis", {}).get("categories") or ["Singapore", "Malaysia", "Indonesia"]
        colors_by_idx = ["#2f6f73", "#7a4c9f", "#9a6a18", "#4f7cac"]
        row_h = (y1 - y0) / max(1, len(labels))
        canvas.setFont("Helvetica", 7)
        for idx, label in enumerate(labels):
            y = y1 - row_h * (idx + 1) + 9
            canvas.setFillColor(colors.black)
            canvas.drawString(x0, y + 6, label)
            bar_x = x0 + 70
            bar_w = (x1 - bar_x) * (0.62 + idx * 0.1 / max(1, len(labels)))
            canvas.setFillColor(colors.HexColor(colors_by_idx[idx % len(colors_by_idx)]))
            canvas.rect(bar_x, y, bar_w, 10, stroke=0, fill=1)

    def _draw_flow_diagram(self, canvas: Canvas, block: FigureBlock) -> None:
        data = block.metadata.get("data", {})
        title = block.metadata.get("title", "Flow diagram")
        x0, y0, x1, y1 = self._draw_figure_frame(canvas, block, title)
        nodes = data.get("nodes", [])[:6]
        if not nodes:
            self._draw_vector_placeholder(canvas, block)
            return
        step = (y1 - y0) / len(nodes)
        box_w = x1 - x0 - 70
        canvas.setFont("Helvetica", 7)
        last_center: tuple[float, float] | None = None
        for idx, node in enumerate(nodes):
            cy = y1 - step * (idx + 0.5)
            bx0 = x0 + 35
            by0 = cy - 8
            canvas.setFillColor(colors.HexColor("#eaf2f0"))
            canvas.setStrokeColor(colors.HexColor("#2f6f73"))
            canvas.roundRect(bx0, by0, box_w, 16, 4, stroke=1, fill=1)
            canvas.setFillColor(colors.black)
            canvas.drawString(bx0 + 5, by0 + 5, str(node.get("label", "Node"))[:65])
            center = (bx0 + box_w / 2, by0)
            if last_center is not None:
                canvas.setStrokeColor(colors.HexColor("#555555"))
                canvas.line(last_center[0], last_center[1] - 3, center[0], by0 + 19)
            last_center = (bx0 + box_w / 2, by0)

    def _draw_regional_map_placeholder(self, canvas: Canvas, block: FigureBlock) -> None:
        title = block.metadata.get("title", "Regional context")
        x0, y0, x1, y1 = self._draw_figure_frame(canvas, block, title)
        nodes = [
            ("Malaysia", x0 + (x1 - x0) * 0.38, y0 + (y1 - y0) * 0.62),
            ("Singapore", x0 + (x1 - x0) * 0.43, y0 + (y1 - y0) * 0.40),
            ("Indonesia", x0 + (x1 - x0) * 0.64, y0 + (y1 - y0) * 0.35),
            ("ASEAN", x0 + (x1 - x0) * 0.73, y0 + (y1 - y0) * 0.72),
        ]
        canvas.setStrokeColor(colors.HexColor("#8c969b"))
        for _, nx, ny in nodes:
            for _, mx, my in nodes:
                if nx < mx:
                    canvas.line(nx, ny, mx, my)
        canvas.setFont("Helvetica", 7)
        for label, nx, ny in nodes:
            canvas.setFillColor(colors.HexColor("#fff1cf"))
            canvas.circle(nx, ny, 14, stroke=1, fill=1)
            canvas.setFillColor(colors.black)
            canvas.drawCentredString(nx, ny - 2, label[:10])
        canvas.setFont("Helvetica", 6)
        canvas.drawString(x0, y0, "Schematic placeholder, not to scale")

    def _draw_vector_placeholder(self, canvas: Canvas, block: FigureBlock) -> None:
        x0, y0, x1, y1 = block.bbox_pt
        canvas.setStrokeColor(colors.HexColor("#2f6f73"))
        canvas.setFillColor(colors.HexColor("#dff3f0"))
        canvas.roundRect(x0, y0, x1 - x0, y1 - y0, 8, stroke=1, fill=1)
