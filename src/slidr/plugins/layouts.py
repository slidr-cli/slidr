"""Layout processing: applies predefined layouts to slide content."""

from slidr.parser.ast import Paragraph, AttrNode, Image

KNOWN_LAYOUTS = {"image-right", "image-left", "two-col"}


def apply_layout(nodes: list, layout: str, render_fn) -> str:
    """Wrap body nodes into columns per the layout definition."""
    if layout not in KNOWN_LAYOUTS:
        return "\n".join(filter(None, (render_fn(n) for n in nodes)))

    if layout == "image-right":
        left, right = _split_image_nodes(nodes)
    elif layout == "image-left":
        right, left = _split_image_nodes(nodes)
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


def _split_image_nodes(nodes: list) -> tuple[list, list]:
    for i, n in enumerate(nodes):
        if isinstance(n, Paragraph) and any(isinstance(t, Image) for t in n.content):
            return nodes[:i] + nodes[i + 1:], [n]
    return nodes, []


def _split_two_col_nodes(nodes: list) -> tuple[list, list]:
    for i, n in enumerate(nodes):
        if isinstance(n, AttrNode) and n.type == "col":
            return nodes[:i], nodes[i + 1:]
    mid = (len(nodes) + 1) // 2
    return nodes[:mid], nodes[mid:]
