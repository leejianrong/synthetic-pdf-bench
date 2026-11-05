from __future__ import annotations

from collections.abc import Sequence

from synthetic_pdf_bench.evaluation.prediction import PredictionDocument
from synthetic_pdf_bench.layout.coordinates import bbox_iou
from synthetic_pdf_bench.schema.truth import DocumentTruth

MIN_IOU = 0.1


def _match(predicted: Sequence[tuple[int | None, list[float] | None]], truth: Sequence[tuple[str, int, list[float]]]) -> dict[int, str]:
    """Greedy one-to-one matching on the same page, highest IoU first: predicted index -> truth id."""
    pairs = sorted(
        ((bbox_iou(box, t_box), i, t_id) for i, (page, box) in enumerate(predicted) if box for t_id, t_page, t_box in truth if t_page == page),
        reverse=True,
    )
    taken_pred, taken_truth, result = set(), set(), {}
    for iou, i, t_id in pairs:
        if iou >= MIN_IOU and i not in taken_pred and t_id not in taken_truth:
            result[i] = t_id
            taken_pred.add(i)
            taken_truth.add(t_id)
    return result


def assign_truth_ids(prediction: PredictionDocument, truth: DocumentTruth) -> PredictionDocument:
    """A real parser cannot know the truth's block, table and figure ids, so give each predicted item the id of the truth item it overlaps most.

    Only the truth geometry is used, never its text or structure, so the block IoU still measures localisation and the table and
    figure scores still measure content. Items that overlap nothing keep their own id and score as misses.
    """
    out = prediction.model_copy(deep=True)
    groups = (
        (out.blocks, "block_id", [(b.block_id, b.page_index, list(b.bbox_pt)) for b in truth.blocks]),
        (out.tables, "table_id", [(t.table_id, t.page_index, list(t.bbox_pt)) for t in truth.tables]),
        (out.figures, "figure_id", [(f.figure_id, f.page_index, list(f.bbox_pt)) for f in truth.figures]),
    )
    for items, field, truth_boxes in groups:
        for i, truth_id in _match([(item.page_index, item.bbox_pt) for item in items], truth_boxes).items():
            setattr(items[i], field, truth_id)
    return out
