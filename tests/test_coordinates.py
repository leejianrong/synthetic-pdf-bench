from synthetic_pdf_bench.layout.coordinates import (
    bbox_iou,
    norm_to_pt_bbox,
    pt_to_norm_bbox,
    pt_to_px_bbox,
    px_to_pt_bbox,
)


def test_point_pixel_bbox_round_trip() -> None:
    bbox_pt = [72, 144, 216, 288]
    page_height_pt = 792
    bbox_px = pt_to_px_bbox(bbox_pt, page_height_pt, 144)
    assert bbox_px == [144, 1008, 432, 1296]
    assert px_to_pt_bbox(bbox_px, page_height_pt, 144) == bbox_pt


def test_point_normalized_bbox_round_trip() -> None:
    bbox_pt = [72, 144, 216, 288]
    bbox_norm = pt_to_norm_bbox(bbox_pt, 612, 792)
    assert norm_to_pt_bbox(bbox_norm, 612, 792) == bbox_pt


def test_bbox_iou() -> None:
    assert bbox_iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0
    assert bbox_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert round(bbox_iou([0, 0, 10, 10], [5, 5, 15, 15]), 4) == 0.1429
