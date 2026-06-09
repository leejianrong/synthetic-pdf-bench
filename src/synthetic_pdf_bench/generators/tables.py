from __future__ import annotations

from html import escape

from synthetic_pdf_bench.schema.blocks import TableBlock, TableCell


def table_to_markdown(matrix: list[list[str]]) -> str:
    header = matrix[0]
    rows = matrix[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def table_to_html(matrix: list[list[str]]) -> str:
    header = "".join(f"<th>{escape(cell)}</th>" for cell in matrix[0])
    body_rows = []
    for row in matrix[1:]:
        body_rows.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>")
    return "<table><thead><tr>" + header + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table>"


def make_simple_table(
    block_id: str, table_id: str, page_index: int, reading_order: int, bbox_pt: list[float]
) -> TableBlock:
    matrix = [
        ["Region", "Revenue", "Accuracy"],
        ["Singapore", "120.5", "0.94"],
        ["Indonesia", "98.3", "0.91"],
        ["Malaysia", "87.4", "0.89"],
    ]
    x0, y0, x1, y1 = bbox_pt
    row_count = len(matrix)
    col_count = len(matrix[0])
    row_h = (y1 - y0) / row_count
    col_w = (x1 - x0) / col_count
    cells: list[TableCell] = []
    idx = 1
    for row_idx, row in enumerate(matrix):
        for col_idx, text in enumerate(row):
            cell_x0 = x0 + col_idx * col_w
            cell_x1 = cell_x0 + col_w
            cell_y1 = y1 - row_idx * row_h
            cell_y0 = cell_y1 - row_h
            cells.append(
                TableCell(
                    cell_id=f"cell_{idx:03d}",
                    row=row_idx,
                    col=col_idx,
                    text=text,
                    bbox_pt=[cell_x0, cell_y0, cell_x1, cell_y1],
                    is_header=row_idx == 0,
                )
            )
            idx += 1
    markdown = table_to_markdown(matrix)
    return TableBlock(
        block_id=block_id,
        page_index=page_index,
        reading_order=reading_order,
        bbox_pt=bbox_pt,
        table_id=table_id,
        matrix=matrix,
        markdown=markdown,
        html=table_to_html(matrix),
        cells=cells,
    )
