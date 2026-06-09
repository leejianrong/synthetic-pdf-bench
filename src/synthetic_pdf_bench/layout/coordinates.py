from __future__ import annotations

from collections.abc import Sequence

POINTS_PER_INCH = 72.0


def pt_to_px_bbox(bbox_pt: Sequence[float], page_height_pt: float, dpi: int) -> list[int]:
    scale = dpi / POINTS_PER_INCH
    x0, y0, x1, y1 = bbox_pt
    return [
        round(x0 * scale),
        round((page_height_pt - y1) * scale),
        round(x1 * scale),
        round((page_height_pt - y0) * scale),
    ]


def px_to_pt_bbox(bbox_px: Sequence[float], page_height_pt: float, dpi: int) -> list[float]:
    scale = POINTS_PER_INCH / dpi
    x0, y0, x1, y1 = bbox_px
    return [
        x0 * scale,
        page_height_pt - (y1 * scale),
        x1 * scale,
        page_height_pt - (y0 * scale),
    ]


def pt_to_norm_bbox(
    bbox_pt: Sequence[float], page_width_pt: float, page_height_pt: float
) -> list[float]:
    x0, y0, x1, y1 = bbox_pt
    return [x0 / page_width_pt, y0 / page_height_pt, x1 / page_width_pt, y1 / page_height_pt]


def norm_to_pt_bbox(
    bbox_norm: Sequence[float], page_width_pt: float, page_height_pt: float
) -> list[float]:
    x0, y0, x1, y1 = bbox_norm
    return [x0 * page_width_pt, y0 * page_height_pt, x1 * page_width_pt, y1 * page_height_pt]


def bbox_iou(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    inter_width = max(0.0, ix1 - ix0)
    inter_height = max(0.0, iy1 - iy0)
    intersection = inter_width * inter_height
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - intersection
    if union == 0:
        return 0.0
    return intersection / union
