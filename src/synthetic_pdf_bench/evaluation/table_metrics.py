from __future__ import annotations

from html.parser import HTMLParser


def table_exact_match(predicted: list[list[str]], expected: list[list[str]]) -> bool:
    normalize = lambda matrix: [[cell.strip() for cell in row] for row in matrix]
    return normalize(predicted) == normalize(expected)


def teds(predicted: list[list[str]] | str, expected: list[list[str]] | str) -> float:
    """Tree-edit-distance similarity: 1 - TED / max(nodes), over table > tr > td trees.

    Inputs are cell matrices or HTML strings (HTML also scores rowspan/colspan). Cells cost their
    normalized text edit distance; any other node change costs 1. See PubTabNet (Zhong et al., 2019).
    """
    a, b = _tree(predicted), _tree(expected)
    return 1 - _tree_edit_distance(a, b) / max(_size(a), _size(b))


class _Node:
    def __init__(self, tag: str, attrs: tuple = (), text: str = "") -> None:
        self.tag, self.attrs, self.text, self.children = tag, attrs, text, []


def _size(node: _Node) -> int:
    return 1 + sum(_size(child) for child in node.children)


def _tree(table: list[list[str]] | str) -> _Node:
    if isinstance(table, str):
        return _html_tree(table)
    root = _Node("table")
    for row in table:
        tr = _Node("tr")
        tr.children = [_Node("td", text=cell.strip()) for cell in row]
        root.children.append(tr)
    return root


def _html_tree(html: str) -> _Node:
    class Builder(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.root, self.stack = _Node("table"), []

        def handle_starttag(self, tag, attrs):
            if tag in ("tr", "td", "th"):
                span = tuple(sorted((k, v) for k, v in attrs if k in ("rowspan", "colspan") and v != "1"))
                node = _Node("tr" if tag == "tr" else "td", span)
                (self.stack[-1] if self.stack else self.root).children.append(node)
                self.stack.append(node)

        def handle_endtag(self, tag):
            if tag in ("tr", "td", "th") and self.stack:
                self.stack.pop()

        def handle_data(self, data):
            if self.stack and self.stack[-1].tag == "td":
                self.stack[-1].text = (self.stack[-1].text + data).strip()

    builder = Builder()
    builder.feed(html)
    return builder.root


def _relabel_cost(a: _Node, b: _Node) -> float:
    if a.tag != b.tag:
        return 1.0
    if a.tag != "td":
        return 0.0
    if a.attrs != b.attrs:
        return 1.0
    longest = max(len(a.text), len(b.text))
    return _edit_distance(a.text, b.text) / longest if longest else 0.0


def _edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _tree_edit_distance(a: _Node, b: _Node) -> float:
    """Zhang-Shasha ordered tree edit distance with unit insert/delete cost."""

    def index(root: _Node):
        nodes, leftmost = [], []

        def visit(node: _Node) -> int:
            first = None
            for child in node.children:
                leaf = visit(child)
                first = leaf if first is None else first
            nodes.append(node)
            leftmost.append(len(nodes) - 1 if first is None else first)
            return leftmost[-1]

        visit(root)
        keyroots = sorted({max(i for i, leaf in enumerate(leftmost) if leaf == value) for value in set(leftmost)})
        return nodes, leftmost, keyroots

    na, la, ka = index(a)
    nb, lb, kb = index(b)
    dist = [[0.0] * len(nb) for _ in na]
    for i in ka:
        for j in kb:
            rows, cols = i - la[i] + 2, j - lb[j] + 2
            forest = [[0.0] * cols for _ in range(rows)]
            for x in range(1, rows):
                forest[x][0] = forest[x - 1][0] + 1
            for y in range(1, cols):
                forest[0][y] = forest[0][y - 1] + 1
            for x in range(1, rows):
                for y in range(1, cols):
                    ii, jj = la[i] + x - 1, lb[j] + y - 1
                    if la[ii] == la[i] and lb[jj] == lb[j]:
                        forest[x][y] = min(
                            forest[x - 1][y] + 1, forest[x][y - 1] + 1, forest[x - 1][y - 1] + _relabel_cost(na[ii], nb[jj])
                        )
                        dist[ii][jj] = forest[x][y]
                    else:
                        forest[x][y] = min(
                            forest[x - 1][y] + 1,
                            forest[x][y - 1] + 1,
                            forest[la[ii] - la[i]][lb[jj] - lb[j]] + dist[ii][jj],
                        )
    return dist[-1][-1]
