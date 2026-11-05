"""Docling (IBM, MIT) with structure: blocks, tables and figures with boxes, not just Markdown. Usage: docling_structured.py PDF OUT_DIR TRUTH_DIR

TRUTH_DIR is read only for item geometry, to give each item the id of the truth item it overlaps (a parser cannot know those ids).
"""
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel, PictureItem, TableItem

from synthetic_pdf_bench.evaluation.matching import assign_truth_ids
from synthetic_pdf_bench.evaluation.prediction import (
    PredictedBlock,
    PredictedFigure,
    PredictedTable,
    PredictionDocument,
)
from synthetic_pdf_bench.schema.truth import DocumentTruth

LABELS = {
    DocItemLabel.TEXT: "paragraph",
    DocItemLabel.PARAGRAPH: "paragraph",
    DocItemLabel.SECTION_HEADER: "heading",
    DocItemLabel.TITLE: "title",
    DocItemLabel.LIST_ITEM: "list_item",
    DocItemLabel.CAPTION: "caption",
    DocItemLabel.FOOTNOTE: "footnote",
    DocItemLabel.FORMULA: "formula",
    DocItemLabel.PAGE_HEADER: "header",
    DocItemLabel.PAGE_FOOTER: "footer",
}


def to_prediction(document) -> PredictionDocument:
    prediction = PredictionDocument(markdown=document.export_to_markdown())
    for item, _ in document.iterate_items():
        if not item.prov:
            continue
        page = item.prov[0].page_no - 1
        box = item.prov[0].bbox.to_bottom_left_origin(document.pages[item.prov[0].page_no].size.height)
        bbox_pt = [box.l, box.b, box.r, box.t]
        n = len(prediction.blocks) + len(prediction.tables) + len(prediction.figures)
        if isinstance(item, TableItem):
            matrix = [[cell.text for cell in row] for row in item.data.grid]
            prediction.tables.append(PredictedTable(table_id=f"table-{n}", matrix=matrix, html=item.export_to_html(document), page_index=page, bbox_pt=bbox_pt))
        elif isinstance(item, PictureItem):
            prediction.figures.append(PredictedFigure(figure_id=f"figure-{n}", page_index=page, bbox_pt=bbox_pt))
        elif item.label in LABELS:
            prediction.blocks.append(PredictedBlock(block_id=f"block-{n}", type=LABELS[item.label], page_index=page, bbox_pt=bbox_pt, text=item.text))
    return prediction


if __name__ == "__main__":
    pdf, out, truth_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    truth = DocumentTruth.model_validate_json((truth_dir / "document.json").read_text(encoding="utf-8"))
    result = assign_truth_ids(to_prediction(DocumentConverter().convert(pdf).document), truth)
    (out / "prediction.json").write_text(result.model_dump_json(), encoding="utf-8")
