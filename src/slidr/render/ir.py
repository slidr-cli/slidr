"""Slide intermediate representation.

Parses a Document AST into resolved, style-annotated slide structures
that both HTML and PPTX renderers consume. Eliminates duplicate node-walking
logic between renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from slidr.parser.ast import (
    Document, Slide, Heading, Paragraph, CodeBlock, Grid, Card,
    Table, Quote, ListNode, AttrNode, Text, Strong, Emphasis,
    Strikethrough, CodeSpan, Image, SoftBreak, Arrow, Notes, Row,
)
from slidr.plugins.layouts import KNOWN_LAYOUTS
from slidr.theme.parser import parse_theme


@dataclass
class Elem:
    """A single styled element on a slide."""
    kind: str
    content: str | list[Any] = ""       # HTML (for HTML renderer)
    text: str = ""                       # plain text (for PPTX renderer)
    # Resolved style properties (for PPTX, informational for HTML)
    font_size: int = 18
    font_weight: str = "normal"
    color: str = "#333"
    bg: str = ""
    accent: str = "#0288d1"
    muted: str = "#777"
    # Structural fields
    level: int = 0
    language: str = ""
    src: str = ""
    alt: str = ""
    header: str = ""
    body: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    tag: str = ""
    class_: str = ""
    cols: int = 0
    children: list[Elem] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    layout: str = ""
    inlines: list[Any] = field(default_factory=list)
    item_inlines: list[list] = field(default_factory=list)
    svg: str = ""
    pdf: bytes = b""


@dataclass
class SlideIR:
    """A fully resolved slide ready for rendering."""
    layout: str = "content"
    elements: list[Elem] = field(default_factory=list)
    notes: str = ""
    variant: str = ""


def build_ir(doc: Document, base_css: str = "", theme_css: str = "") -> list[SlideIR]:
    """Convert a Document AST into a list of SlideIR objects."""
    styles = resolve_styles(base_css, theme_css) if base_css else {}
    slides = []
    for slide in doc.slides:
        layout = slide.layout
        body_nodes = slide.children

        heading_elem = None
        if body_nodes and isinstance(body_nodes[0], Heading) and body_nodes[0].level <= 2:
            heading_elem = _convert_node(body_nodes[0], styles)
            body_nodes = body_nodes[1:]

        if layout in KNOWN_LAYOUTS:
            elements = _apply_layout_ir(body_nodes, layout, styles)
        else:
            elements = [_convert_node(n, styles) for n in body_nodes]

        if heading_elem:
            elements.insert(0, heading_elem)

        slides.append(SlideIR(layout=layout, elements=elements, notes=slide.notes or "",
                             variant=slide.variant or ""))
    return slides


def resolve_styles(base_css: str, theme_css: str) -> dict:
    """Parse CSS into resolved style properties for IR elements."""
    s = parse_theme(base_css, theme_css)
    s["ink_rgb_hex"] = _rgb_to_hex(s.get("ink_rgb", (51, 51, 51)))
    s["muted_rgb_hex"] = _rgb_to_hex(s.get("muted_rgb", (119, 119, 119)))
    s["accent_rgb_hex"] = _rgb_to_hex(s.get("accent_rgb", (2, 136, 209)))
    return s


def _rgb_to_hex(rgb: tuple) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _apply_layout_ir(nodes: list, layout: str, styles: dict) -> list[Elem]:
    """Apply layout column wrapping at the IR level."""
    extra = []
    arrow_elem = None
    if layout == "image-right":
        left, right = _split_image_ir(nodes)
    elif layout == "image-left":
        right, left = _split_image_ir(nodes)
    elif layout == "two-col":
        left, right = _split_two_col_ir(nodes)
    elif layout == "compare":
        # Card | Arrow | Card  →  col-left, arrow, col-right
        # Notes nodes stay as extra below
        arrow_idx = next((i for i, n in enumerate(nodes) if isinstance(n, Arrow)), None)
        extra = [n for n in nodes if isinstance(n, Notes)]
        if arrow_idx is not None and arrow_idx > 0 and arrow_idx < len(nodes) - 1:
            left = nodes[:arrow_idx]
            right = nodes[arrow_idx + 1:]
            right = [n for n in right if not isinstance(n, Notes)]
            arrow_elem = _convert_node(nodes[arrow_idx], styles)
        else:
            left, right = _split_two_col_ir(nodes)
            arrow_elem = None
    else:
        return [_convert_node(n, styles) for n in nodes]

    children = []
    if left:
        children.append(_col_elem("left", left, styles))
    if arrow_elem is not None:
        children.append(arrow_elem)
    if right:
        children.append(_col_elem("right", right, styles))
    cls = "layout-cols"
    if layout == "compare":
        cls += " compare"
    result = [Elem(kind="grid", layout=cls, cols=0, children=children)]
    if extra:
        result.extend(_convert_node(n, styles) for n in extra)
    return result


def _col_elem(side: str, nodes: list, styles: dict) -> Elem:
    children = [_convert_node(n, styles) for n in nodes]
    return Elem(kind="grid", layout=f"col-{side}", cols=0, children=children)


def _split_image_ir(nodes: list) -> tuple[list, list]:
    col_idx = _find_col(nodes)
    if col_idx >= 0:
        return nodes[:col_idx], nodes[col_idx + 1:]
    for i, n in enumerate(nodes):
        if isinstance(n, Paragraph) and any(isinstance(t, Image) for t in n.content):
            return nodes[:i] + nodes[i + 1:], [n]
    return nodes, []


def _split_two_col_ir(nodes: list) -> tuple[list, list]:
    col_idx = _find_col(nodes)
    if col_idx >= 0:
        left, right = nodes[:col_idx], nodes[col_idx + 1:]
    else:
        left, right = nodes, []
    # Group @row-separated elements into horizontal rows
    left = _group_rows_ir(left)
    right = _group_rows_ir(right)
    return left, right


def _group_rows_ir(nodes: list) -> list:
    """Group @row-separated elements into horizontal Rows."""
    from slidr.parser.ast import AttrNode, Row
    row_indices = [i for i, n in enumerate(nodes)
                   if isinstance(n, AttrNode) and n.type == "row"]
    if not row_indices:
        return list(nodes)
    # Everything from first element to last (between @row markers) goes in Row
    result = []
    start = 0
    for ri in row_indices:
        if ri > start:
            result.extend(nodes[start:ri])
            start = ri + 1
    if start < len(nodes):
        result.extend(nodes[start:])
    # Wrap if we collected multiple
    if len(result) > 1:
        return [Row(children=list(result))]
    return result


def _find_col(nodes: list) -> int:
    for i, n in enumerate(nodes):
        if isinstance(n, AttrNode) and n.type == "col":
            return i
    return -1


def _normalize_viewbox(svg: str) -> str:
    """Normalize negative viewBox origin to 0,0, expanding dimensions."""
    import re
    m = re.search(r'viewBox="([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)"', svg)
    if not m:
        return svg
    x, y, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    if x >= 0 and y >= 0:
        return svg
    new_w, new_h = w + abs(x), h + abs(y)
    return svg.replace(m.group(0), f'viewBox="0 0 {new_w:g} {new_h:g}"', 1)


def _convert_node(node, styles: dict) -> Elem:
    """Convert a single AST node to an IR element with resolved styles."""
    base = Elem(kind="text", content="",
                font_size=styles.get("font_body", 18),
                color=styles.get("ink_rgb_hex", "#333"),
                accent=styles.get("accent_rgb_hex", "#0288d1"),
                muted=styles.get("muted_rgb_hex", "#777"))

    if isinstance(node, Heading):
        fs = {1: styles.get("font_h1", 63), 2: styles.get("font_h2", 36), 3: styles.get("font_h3", 18)}.get(node.level, 18)
        return Elem(kind="heading", content=_render_inline_html(node.content),
                    text=_render_inline_text(node.content),
                    inlines=node.content,
                    level=node.level, font_size=fs, color=base.color)
    elif isinstance(node, Paragraph):
        return Elem(kind="text", content=_render_inline_html(node.content),
                    text=_render_inline_text(node.content),
                    inlines=node.content,
                    font_size=base.font_size, color=base.color)
    elif isinstance(node, CodeBlock):
        fs = styles.get("font_code", 14)
        svg = ""
        pdf = b""
        if node.language == "seaborn":
            from slidr.render.seaborn import render_seaborn_svg
            svg = render_seaborn_svg(node.content) or ""
        elif node.language == "mermaid":
            try:
                from mmdc import render as render_mmd
                d = render_mmd(node.content)
                svg = _normalize_viewbox(d.svg())
                pdf = d.pdf()
            except Exception:
                svg = ""
                pdf = b""
        elif node.language == "dot":
            from slidr.render.dot import render_dot_svg
            fam = styles.get("font_body_family", "")
            size = styles.get("font_body", 18)
            svg = render_dot_svg(node.content, font_family=fam, font_size=size) or ""
        return Elem(kind="code", content=node.content, text=node.content,
                    language=node.language, font_size=fs, svg=svg, pdf=pdf)
    elif isinstance(node, ListNode):
        items_html = [_render_inline_html(item) for item in node.items]
        items_text = [_render_inline_text(item) for item in node.items]
        fs = styles.get("font_li", 16)
        return Elem(kind="list", content=items_html, text=">".join(items_text),
                    items=items_text,
                    item_inlines=[list(item) for item in node.items],
                    font_size=fs, color=base.color)
    elif isinstance(node, Table):
        return Elem(kind="table", headers=node.headers, rows=node.rows)
    elif isinstance(node, Quote):
        fs = styles.get("font_quote", 24)
        return Elem(kind="quote", content=_render_inline_html(node.content),
                    text=_render_inline_text(node.content),
                    inlines=node.content,
                    font_size=fs, color=base.muted, accent=base.accent)
    elif isinstance(node, Grid):
        children = [_convert_node(c, styles) for c in node.children]
        return Elem(kind="grid", cols=node.cols, class_=node.class_ or "", children=children)
    elif isinstance(node, Card):
        return Elem(kind="card", header=node.header, body=node.body,
                    tag=node.tag or "", class_=node.class_ or "",
                    font_size=base.font_size, color=base.color)
    elif isinstance(node, Arrow):
        content = node.content.strip()
        if not content:
            content = "\u2192"
        # Check if content is an image reference
        if content.startswith("!["):
            from markdown_it import MarkdownIt
            md = MarkdownIt()
            tokens = md.parseInline(content)
            html = ""
            for t in tokens:
                if t.type == "image":
                    html = f'<img src="{t.attrs.get("src", "")}" alt="{t.attrs.get("alt", "arrow")}">'
                    break
            if html:
                return Elem(kind="arrow", content=html, text=html, font_size=20,
                            color=base.muted)
        return Elem(kind="arrow", content=content, text=content, font_size=20,
                    color=base.muted)
    elif isinstance(node, Row):
        children = [_convert_node(c, styles) for c in node.children]
        return Elem(kind="row", children=children)
    elif isinstance(node, Notes):
        return Elem(kind="notes", content=node.content, tag=node.tag or "")
    elif isinstance(node, AttrNode):
        if node.type == "speaker":
            name = node.attrs.get("name", node.value)
            role = node.attrs.get("role", "")
            text = f"{name}\n{role}" if role else name
            return Elem(kind="speaker", content=_escape(node.value), text=text,
                        attrs=node.attrs,
                        font_size=styles.get("font_speaker", 18), color=base.color)
        elif node.type == "kicker":
            return Elem(kind="kicker", content=_escape(node.value), text=node.value,
                        font_size=styles.get("font_kicker", 14), color=base.accent)
        elif node.type == "subtitle":
            return Elem(kind="subtitle", content=_escape(node.value), text=node.value,
                        font_size=styles.get("font_subtitle", 32), color=base.muted)
        elif node.type == "tiny":
            fs = styles.get("font_small", 13)
            return Elem(kind="tiny", content=_escape(node.value), text=node.value,
                        font_size=fs, color=base.muted)
        return Elem(kind="text", content=_escape(node.value), text=node.value)
    return Elem(kind="text", content="", text="")


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_inline_html(nodes: list) -> str:
    """Render inline AST nodes to HTML (preserves formatting)."""
    s = ""
    for n in nodes:
        if isinstance(n, Text):
            s += _escape(n.content)
        elif isinstance(n, Strong):
            s += f"<strong>{_render_inline_html(n.children)}</strong>"
        elif isinstance(n, Emphasis):
            s += f"<em>{_render_inline_html(n.children)}</em>"
        elif isinstance(n, Strikethrough):
            s += f"<s>{_render_inline_html(n.children)}</s>"
        elif isinstance(n, CodeSpan):
            s += f"<code>{_escape(n.content)}</code>"
        elif isinstance(n, Image):
            title = f' title="{_escape(n.title)}"' if n.title else ""
            s += f'<img src="{_escape(n.src)}" alt="{_escape(n.alt)}"{title}>'
        elif isinstance(n, SoftBreak):
            s += " "
    return s


def _render_inline_text(nodes: list) -> str:
    """Render inline AST nodes to plain text (for PPTX use)."""
    s = ""
    for n in nodes:
        if isinstance(n, Text):
            s += n.content
        elif isinstance(n, (Strong, Emphasis, Strikethrough)):
            s += _render_inline_text(n.children)
        elif isinstance(n, CodeSpan):
            s += n.content
        elif isinstance(n, Image):
            s += f"[{n.alt or 'image'}]"
        elif isinstance(n, SoftBreak):
            s += " "
    return s
