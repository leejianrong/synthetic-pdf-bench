from __future__ import annotations

from synthetic_pdf_bench.schema.blocks import Block, FigureBlock, TableBlock


def block_to_markdown(block: Block | TableBlock | FigureBlock) -> str:
    if isinstance(block, TableBlock):
        return block.markdown
    if isinstance(block, FigureBlock):
        return block.markdown_ref or block.markdown
    if block.markdown:
        return block.markdown
    if block.type == "title":
        return f"# {block.text}"
    if block.type == "heading":
        return f"## {block.text}"
    if block.type == "caption":
        return f"*{block.text.rstrip('.')}.*"
    return block.text


def write_markdown(blocks: list[Block | TableBlock | FigureBlock]) -> str:
    included = [block for block in blocks if block.include_in_markdown]
    chunks: list[str] = []
    cursor = 0
    previous = None
    for block in included:
        markdown = block_to_markdown(block).strip()
        if not markdown:
            block.markdown_span = None
            continue
        if chunks:
            gap = "\n" if previous == block.type == "list_item" else "\n\n"  # list items form one tight list
            chunks.append(gap)
            cursor += len(gap)
        previous = block.type
        start = cursor
        chunks.append(markdown)
        cursor += len(markdown)
        block.markdown = markdown
        block.markdown_span = [start, cursor]
    return "".join(chunks) + ("\n" if chunks else "")
