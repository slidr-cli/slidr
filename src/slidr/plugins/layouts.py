"""Layout processing: applies predefined layouts to slide content."""

from slidr.parser.ast import Paragraph, AttrNode, Image

KNOWN_LAYOUTS = {"image-right", "image-left", "two-col"}


def apply_layout(nodes: list, layout: str, render_fn) -> str:
    """Wrap body nodes into columns per the layout definition."""
    if layout not in KNOWN_LAYOUTS:
        return "\n".join(filter(None, (render_fn(n) for n in nodes)))

    if layout == "image-right":
        left, right = _split_col_or_image(nodes, flip=False)
    elif layout == "image-left":
        left, right = _split_col_or_image(nodes, flip=True)
    elif layout == "two-col":
        left, right = _split_two_col_nodes(nodes)
    else:
        return "\n".join(filter(None, (render_fn(n) for n in nodes)))

    left_html = "\n".join(filter(None, (render_fn(n) for n in left)))
    right_html = "\n".join(filter(None, (render_fn(n) for n in right)))
    parts = []
    if left_html or right_html:
        parts.append('<div class="layout-cols">')
        parts.append('<div class="col-left">\n' + left_html + '\n</div>')
        if right_html:
            parts.append('<div class="col-right">\n' + right_html + '\n</div>')
        parts.append('</div>')
    return "\n".join(parts)


def _split_col_or_image(nodes: list, flip: bool = False) -> tuple[list, list]:
    col_idx = _find_col(nodes)
    if col_idx >= 0:
        left, right = nodes[:col_idx], nodes[col_idx + 1:]
        return (right, left) if flip else (left, right)
    return _split_image_nodes(nodes, flip)


def _split_image_nodes(nodes: list, flip: bool = False) -> tuple[list, list]:
    for i, n in enumerate(nodes):
        if isinstance(n, Paragraph) and any(isinstance(t, Image) for t in n.content):
            left, right = nodes[:i] + nodes[i + 1:], [n]
            return (right, left) if flip else (left, right)
    return (nodes, []) if not flip else ([], nodes)


def _split_two_col_nodes(nodes: list) -> tuple[list, list]:
    col_idx = _find_col(nodes)
    if col_idx >= 0:
        return nodes[:col_idx], nodes[col_idx + 1:]
    mid = (len(nodes) + 1) // 2
    return nodes[:mid], nodes[mid:]


def _find_col(nodes: list) -> int:
    for i, n in enumerate(nodes):
        if isinstance(n, AttrNode) and n.type == "col":
            return i
    return -1
