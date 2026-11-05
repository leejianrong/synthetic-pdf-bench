from __future__ import annotations

from pathlib import Path
from random import Random
from tempfile import gettempdir
from zlib import crc32

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt
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


def make_photo_figure(seed: int, figure_id: str) -> Path:
    """A continuous-tone, full-colour picture. Real DocLayNet pictures are mostly photographs, not flat diagrams."""
    path = Path(gettempdir()) / f"synthetic_pdf_bench_photo_{figure_id}_{seed}.png"
    rng = np.random.default_rng(seed * 100003 + crc32(figure_id.encode()))
    height, width = 340, 720
    field = np.zeros((height, width))
    for octave, weight in enumerate((1.0, 0.5, 0.25, 0.125)):  # value noise: coarse grids upsampled smoothly, finer ones added on top
        cells = 3 * 2**octave
        grid = rng.random((cells + 1, int(cells * width / height) + 1))
        field += weight * np.asarray(Image.fromarray((grid * 255).astype(np.uint8)).resize((width, height), Image.BICUBIC)) / 255
    field = (field - field.min()) / (field.max() - field.min())
    dark, light = rng.random(3) * 0.5, 0.5 + rng.random(3) * 0.5
    pixels = dark + field[..., None] * (light - dark)
    for _ in range(int(rng.integers(2, 6))):  # soft coloured blobs stand in for objects
        cy, cx, ry, rx = rng.integers(0, height), rng.integers(0, width), rng.integers(30, 110), rng.integers(40, 160)
        yy, xx = np.ogrid[:height, :width]
        mask = np.clip(1 - (((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2), 0, 1)[..., None]
        pixels = pixels * (1 - mask) + rng.random(3) * mask
    pixels += rng.normal(0, 0.02, pixels.shape)  # sensor grain
    Image.fromarray((np.clip(pixels, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def make_matplotlib_figure(kind: str, data: dict, seed: int, figure_id: str) -> Path:
    path = Path(gettempdir()) / f"synthetic_pdf_bench_{figure_id}_{seed}.png"
    rng = Random(seed + sum(ord(char) for char in figure_id))
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=120)
    if kind == "bar_chart":
        _draw_bar_chart(ax, data)
    elif kind == "line_chart":
        _draw_line_chart(ax, data)
    elif kind == "stacked_bar":
        _draw_stacked_bar(ax, data)
    elif kind == "timeline":
        _draw_timeline(ax, data)
    elif kind == "scatter_plot":
        _draw_scatter_plot(ax, data, rng)
    elif kind == "heatmap":
        _draw_heatmap(ax, data)
    else:
        _draw_bar_chart(ax, data)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def _labels(data: dict) -> list[str]:
    return data.get("labels") or ["Singapore", "Malaysia", "Indonesia"]


def _series(data: dict) -> list[float]:
    return data.get("values") or [88, 74, 69]


def _draw_bar_chart(ax, data: dict) -> None:
    labels = _labels(data)
    values = _series(data)
    ax.bar(labels, values, color=["#2f6f73", "#7a4c9f", "#9a6a18", "#4f7cac"][: len(labels)])
    ax.set_ylabel(data.get("y_label", "Index"))
    ax.set_title(data.get("title", "Comparative bar chart"))
    ax.grid(axis="y", alpha=0.25)


def _draw_line_chart(ax, data: dict) -> None:
    years = data.get("years") or [1960, 1970, 1980, 1990, 2000, 2010, 2020]
    series = data.get("series") or {
        "Singapore": [20, 35, 55, 72, 83, 91, 96],
        "Malaysia": [18, 28, 42, 55, 68, 78, 84],
        "Indonesia": [12, 19, 31, 43, 56, 67, 75],
    }
    for label, values in series.items():
        ax.plot(years, values, marker="o", linewidth=1.8, label=label)
    ax.set_title(data.get("title", "Trend over time"))
    ax.set_xlabel(data.get("x_label", "Year"))
    ax.set_ylabel(data.get("y_label", "Index"))
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)


def _draw_stacked_bar(ax, data: dict) -> None:
    labels = _labels(data)
    series = data.get("series") or {
        "Services": [55, 42, 38],
        "Manufacturing": [25, 34, 29],
        "Resources": [5, 14, 23],
    }
    bottoms = [0.0] * len(labels)
    palette = ["#2f6f73", "#7a4c9f", "#9a6a18", "#4f7cac", "#c45b4b"]
    for idx, (name, values) in enumerate(series.items()):
        ax.bar(labels, values, bottom=bottoms, label=name, color=palette[idx % len(palette)])
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]
    ax.set_title(data.get("title", "Stacked composition"))
    ax.set_ylabel(data.get("y_label", "Share"))
    ax.legend(fontsize=7)


_TIMELINE_LANES = [0.12, -0.18, 0.26, -0.32, 0.40, -0.46]


def _draw_timeline(ax, data: dict) -> list:
    """Draw the timeline and return its label texts. Each label takes the first height lane where it clears the labels already placed."""
    events = data.get("events") or [
        {"year": 1945, "label": "Indonesia"},
        {"year": 1957, "label": "Malaya"},
        {"year": 1965, "label": "Singapore"},
        {"year": 1998, "label": "Reformasi"},
    ]
    years = [event["year"] for event in events]
    ax.hlines(1, min(years) - 5, max(years) + 5, color="#8c969b")
    ax.scatter(years, [1] * len(years), color="#2f6f73")
    ax.set_ylim(0.5, 1.5)
    ax.set_yticks([])
    ax.set_title(data.get("title", "Timeline"))
    renderer = ax.figure.canvas.get_renderer()
    placed: list = []
    for event in sorted(events, key=lambda e: e["year"]):
        for lane in _TIMELINE_LANES:
            text = ax.text(event["year"], 1 + lane, event["label"], ha="center", fontsize=7)
            box = text.get_window_extent(renderer)
            if not any(box.overlaps(other.get_window_extent(renderer)) for other in placed):
                break
            text.remove()
        else:
            text = ax.text(event["year"], 1 + _TIMELINE_LANES[-1], event["label"], ha="center", fontsize=7)
        placed.append(text)
    return placed


def _draw_scatter_plot(ax, data: dict, rng: Random) -> None:
    groups = data.get("groups") or ["Singapore", "Malaysia", "Indonesia"]
    for idx, group in enumerate(groups):
        xs = [rng.uniform(0.1, 1.0) + idx * 0.08 for _ in range(18)]
        ys = [x * (0.65 + idx * 0.12) + rng.uniform(0.0, 0.3) for x in xs]
        ax.scatter(xs, ys, s=18, alpha=0.75, label=group)
    ax.set_title(data.get("title", "Synthetic scatter plot"))
    ax.set_xlabel(data.get("x_label", "Urbanization proxy"))
    ax.set_ylabel(data.get("y_label", "Development proxy"))
    ax.grid(alpha=0.2)
    ax.legend(fontsize=7)


def _draw_heatmap(ax, data: dict) -> None:
    matrix = data.get("matrix") or [
        [0.8, 0.6, 0.5, 0.7],
        [0.5, 0.7, 0.8, 0.6],
        [0.4, 0.6, 0.7, 0.9],
    ]
    row_labels = data.get("row_labels") or ["Singapore", "Malaysia", "Indonesia"]
    col_labels = data.get("col_labels") or ["Politics", "Economy", "Society", "Region"]
    im = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(col_labels)), col_labels, rotation=25, ha="right")
    ax.set_yticks(range(len(row_labels)), row_labels)
    ax.set_title(data.get("title", "Qualitative heatmap"))
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
