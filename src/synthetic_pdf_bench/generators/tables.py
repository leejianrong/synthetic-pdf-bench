from __future__ import annotations

from html import escape

from synthetic_pdf_bench.schema.blocks import TableBlock, TableCell


TableVariant = str


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


def table_variant_names() -> list[str]:
    return [
        "narrow",
        "wide",
        "numeric",
        "multilingual",
        "wrapped_cell_text",
        "merged_cell_approximation",
        "multi_page",
    ]


def make_table_variant_matrix(variant: TableVariant, seed: int = 1) -> tuple[list[list[str]], list[dict]]:
    if variant == "narrow":
        return [["Country", "Theme"], ["Singapore", "Port city"], ["Malaysia", "Federal economy"], ["Indonesia", "Archipelago"]], []
    if variant == "wide":
        return [
            ["Country", "Politics", "Economy", "Society", "Language", "Regional Role"],
            ["Singapore", "Parliamentary republic", "Advanced services", "Urban planning", "Multilingual", "Hub"],
            ["Malaysia", "Federal monarchy", "Manufacturing and commodities", "Urban corridors", "Bahasa Malaysia", "Connector"],
            ["Indonesia", "Presidential republic", "Large domestic market", "Decentralized urbanization", "Bahasa Indonesia", "Scale"],
        ], []
    if variant == "numeric":
        return [
            ["Country", "1900s Index", "1960s Index", "2000s Index", "Recent Index"],
            ["Singapore", "18.2", "45.0", "88.4", "94.1"],
            ["Malaysia", "21.5", "39.7", "72.6", "81.3"],
            ["Indonesia", "16.4", "31.9", "63.8", "75.5"],
        ], []
    if variant == "multilingual":
        return [
            ["Country", "English", "Malay/Indonesian", "Chinese"],
            ["Singapore", "diverse society", "masyarakat majmuk", "多元社会"],
            ["Malaysia", "independence", "merdeka", "独立"],
            ["Indonesia", "development", "pembangunan", "发展"],
        ], []
    if variant == "wrapped_cell_text":
        return [
            ["Country", "Long Description", "Benchmark Purpose"],
            [
                "Singapore",
                "Compact city-state with a long-standing port, public housing, logistics, finance, and multilingual administration.",
                "Tests wrapped text in a narrow table cell.",
            ],
            [
                "Malaysia",
                "Federal country with peninsular and Bornean regions, varied urban corridors, commodities, manufacturing, and services.",
                "Tests multi-line cell rendering.",
            ],
            [
                "Indonesia",
                "Large archipelagic republic with regional diversity, decentralization, infrastructure expansion, resources, and services.",
                "Tests long text extraction.",
            ],
        ], []
    if variant == "merged_cell_approximation":
        return [
            ["Theme", "Singapore", "Malaysia", "Indonesia"],
            ["Politics", "Republic", "Federal monarchy", "Republic"],
            ["Economy", "Services hub", "Mixed economy", "Domestic scale"],
            ["Society", "Urban multilingual", "Multicultural", "Archipelagic diversity"],
        ], [{"row": 0, "col": 0, "rowspan": 1, "colspan": 4, "text": "Regional Comparison Header"}]
    if variant == "multi_page":
        rows = [["Year", "Singapore", "Malaysia", "Indonesia"]]
        for index in range(1, 85):
            year = 1900 + index
            rows.append([str(year), f"{50 + index % 37}", f"{45 + index % 41}", f"{40 + index % 47}"])
        return rows, []
    raise ValueError(f"unknown table variant: {variant}")


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
