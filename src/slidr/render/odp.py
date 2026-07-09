"""ODP renderer consuming SlideIR."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from itertools import count
from pathlib import Path
from typing import Any

from odfdo import (
    Document,
    DrawPage,
    Frame,
    Paragraph,
    Span,
    Style,
    Table,
)
from odfdo.element import Element

from slidr.parser.ast import Document as ASTDocument
from slidr.render.ir import Elem, SlideIR, build_ir


@dataclass(frozen=True)
class StyleKey:
    font_size: int = 18
    color: str = "#333333"
    font_weight: str = "normal"
    font_style: str = "normal"
    font_family: str = "Liberation Sans"
    fill: str = ""
    text_align: str = "left"
    padding: str = "0cm"


@dataclass(frozen=True)
class TextStyleKey:
    weight: str = "normal"
    font_style: str = "normal"
    font_family: str = ""
    font_size: int = 0


@dataclass
class LayoutContext:
    x: float = 0.0
    y: float = 0.0
    width: float = 24.0
    page_width: float = 28.0
    page_height: float = 15.75
    margin_left: float = 2.0
    margin_top: float = 2.0
    gap: float = 0.5
    source_dir: Path | None = None


class GraphicStyleRegistry:
    def __init__(self) -> None:
        self._styles: dict[StyleKey, str] = {}
        self._counter = count(1)

    def register(self, key: StyleKey) -> str:
        if key not in self._styles:
            self._styles[key] = f"SlidrG_{next(self._counter):03d}"
        return self._styles[key]

    def insert_all(self, document: Document) -> None:
        for key, name in self._styles.items():
            kwargs: dict[str, str] = {}
            if key.fill:
                kwargs["fill_color"] = key.fill
            style = Style(
                "graphic",
                name=name,
                stroke="none",
                padding_top=key.padding,
                padding_bottom=key.padding,
                padding_left=key.padding,
                padding_right=key.padding,
                **kwargs,
            )
            style.set_properties(area="paragraph", text_align=key.text_align)
            style.set_properties(
                area="text",
                color=key.color,
                font=key.font_family,
                font_family=key.font_family,
                size=f"{key.font_size}pt",
                weight=key.font_weight,
                font_style=key.font_style,
            )
            document.insert_style(style)


class TextStyleRegistry:
    def __init__(self) -> None:
        self._styles: dict[TextStyleKey, str] = {}
        self._counter = count(1)

    def register(self, key: TextStyleKey) -> str:
        if key not in self._styles:
            self._styles[key] = f"SlidrT_{next(self._counter):03d}"
        return self._styles[key]

    def insert_all(self, document: Document) -> None:
        for key, name in self._styles.items():
            style = Style(
                "text",
                name=name,
                bold=(key.weight == "bold"),
                italic=(key.font_style == "italic"),
            )
            if key.font_family:
                style.set_properties(area="text", font=key.font_family)
            if key.font_size:
                style.set_properties(area="text", size=f"{key.font_size}pt")
            document.insert_style(style)


def _child_ctx(parent: LayoutContext, **overrides: Any) -> LayoutContext:
    return replace(parent, **overrides)


_table_seq = count(1)


def _next_table_id() -> int:
    return next(_table_seq)


_TAG_COLORS: dict[str, str] = {
    "green": "#e8f5e9",
    "red": "#ffebee",
    "blue": "#e3f2fd",
    "yellow": "#fff9c4",
    "orange": "#fff3e0",
    "purple": "#f3e5f5",
    "": "#e3f2fd",
}


def _tag_to_color(tag: str) -> str:
    return _TAG_COLORS.get(tag, "#e3f2fd")


# ---------------------------------------------------------------------------
# Style key factory
# ---------------------------------------------------------------------------


def _style_key_for(elem: Elem) -> StyleKey:
    family = "Liberation Mono" if elem.kind == "code" else "Liberation Sans"
    weight = "bold" if elem.kind in ("heading", "kicker") else "normal"
    fstyle = "italic" if elem.kind == "quote" else "normal"
    align = "center" if elem.kind == "subtitle" else "left"
    color = elem.color
    if elem.kind in ("quote", "subtitle", "tiny"):
        color = elem.muted
    return StyleKey(
        font_size=elem.font_size,
        color=color,
        font_weight=weight,
        font_style=fstyle,
        font_family=family,
        fill="",
        text_align=align,
        padding="0cm",
    )


# ---------------------------------------------------------------------------
# Rich text paragraph builder
# ---------------------------------------------------------------------------


def _build_paragraph(inlines: list, tr: TextStyleRegistry) -> Paragraph:
    from slidr.parser.ast import (
        Text,
        Strong,
        Emphasis,
        Strikethrough,
        CodeSpan,
        SoftBreak,
        Image,
    )

    p = Paragraph()
    for node in inlines:
        if isinstance(node, Text):
            p.append(node.content)
        elif isinstance(node, Strong):
            name = tr.register(TextStyleKey(weight="bold"))
            for c in _walk_text_children(node.children):
                if isinstance(c, str):
                    p.append(Span(c, style=name))
        elif isinstance(node, Emphasis):
            name = tr.register(TextStyleKey(font_style="italic"))
            for c in _walk_text_children(node.children):
                if isinstance(c, str):
                    p.append(Span(c, style=name))
        elif isinstance(node, Strikethrough):
            text = "".join(
                c if isinstance(c, str) else ""
                for c in _walk_text_children(node.children)
            )
            p.append(text)
        elif isinstance(node, CodeSpan):
            name = tr.register(
                TextStyleKey(font_family="Liberation Mono", font_size=14)
            )
            p.append(Span(node.content, style=name))
        elif isinstance(node, Image):
            p.append(f" [{node.alt or 'image'}] ")
        elif isinstance(node, SoftBreak):
            p.append(" ")
    return p


def _walk_text_children(children: list) -> list:
    from slidr.parser.ast import (
        Text,
        Strong,
        Emphasis,
        Strikethrough,
        CodeSpan,
    )

    result: list = []
    for child in children:
        if isinstance(child, Text):
            result.append(child.content)
        elif isinstance(child, (Strong, Emphasis, Strikethrough)):
            result.extend(_walk_text_children(child.children))
        elif isinstance(child, CodeSpan):
            result.append(child.content)
    return result


# ---------------------------------------------------------------------------
# Height estimation
# ---------------------------------------------------------------------------


def _estimate_text_height(text: str, font_size: int, width_cm: float) -> float:
    if not text:
        return 0.0
    width_pt = width_cm / 0.0353
    char_width_pt = font_size * 0.5
    chars_per_line = max(1, int(width_pt / char_width_pt))
    lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
    line_height_pt = font_size * 1.4
    return (lines * line_height_pt) * 0.0353


def _estimate_elem_height(elem: Elem, width_cm: float) -> float:
    kind = elem.kind
    if kind in (
        "heading", "text", "quote", "code", "kicker", "subtitle", "tiny"
    ):
        return _estimate_text_height(elem.text, elem.font_size, width_cm) + 0.5
    elif kind == "list":
        h = 0.0
        for item in elem.items:
            h += _estimate_text_height(item, elem.font_size, width_cm - 0.8) + 0.2
        return h + 0.5
    elif kind == "table":
        return 0.6 * (len(elem.rows) + 1) + 0.5
    elif kind == "grid":
        cols = elem.cols or len(elem.children) or 2
        if cols <= 0:
            cols = 1
        col_w = (width_cm - 0.5 * (cols - 1)) / cols
        max_h = 0.0
        for child in elem.children:
            max_h = max(max_h, _estimate_elem_height(child, col_w))
        return max_h + 0.5
    elif kind == "card":
        lines = (1 if elem.header else 0) + len(elem.body) + 1
        return lines * 1.2 + 0.5
    elif kind == "speaker":
        return (2.5 if elem.attrs.get("role") else 1.5) + 0.5
    return 0.5


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _is_image_elem(elem: Elem) -> bool:
    from slidr.parser.ast import Image as ASTImage

    return (
        elem.kind == "text"
        and len(elem.inlines) == 1
        and isinstance(elem.inlines[0], ASTImage)
    )


def _image_natural_size(path: str) -> tuple[float, float]:
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as im:
            w_px, h_px = im.size
        return (w_px * 2.54 / 72, h_px * 2.54 / 72)
    except Exception:
        return (16.0, 9.0)


def _resolve_img_path(src: str, source_dir: Path | None) -> str | None:
    """Resolve an image src relative to the markdown file's directory."""
    if not src:
        return None
    if os.path.isabs(src):
        return src
    if source_dir:
        return str((source_dir / src).resolve())
    return src if os.path.isfile(src) else None


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------


def _render_fallback_text(elem: Elem, ctx, gr, tr, odp):
    """Render as plain text, ignoring image detection to avoid recursion."""
    if not elem.text.strip():
        return []
    key = _style_key_for(elem)
    gname = gr.register(key)
    height = _estimate_text_height(elem.text, elem.font_size, ctx.width)
    p = Paragraph(elem.text)
    frame = Frame.text_frame(
        p,
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]


def _render_image(elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
                  tr: TextStyleRegistry, odp: Document) -> list[Element]:
    img = elem.inlines[0]
    img_path = _resolve_img_path(img.src, ctx.source_dir)
    if not img_path or not os.path.isfile(img_path):
        return _render_fallback_text(elem, ctx, gr, tr, odp)
    uri = odp.add_file(img_path)
    size_cm = _image_natural_size(img_path)
    if size_cm[0] > ctx.width:
        scale = ctx.width / size_cm[0]
        size_cm = (ctx.width, size_cm[1] * scale)
    height = size_cm[1]
    frame = Frame.image_frame(
        image=uri,
        text=img.title or "",
        size=(f"{size_cm[0]:.2f}cm", f"{size_cm[1]:.2f}cm"),
        position=(
            f"{ctx.x + (ctx.width - size_cm[0]) / 2:.2f}cm",
            f"{ctx.y:.2f}cm",
        ),
        anchor_type="page",
    )
    if img.title:
        frame.svg_title = img.title
    if img.alt:
        frame.svg_description = img.alt
    ctx.y += height + ctx.gap
    return [frame]


def _render_seaborn_odp(
    elem: Elem, ctx: LayoutContext, odp: Document
) -> list[Element]:
    from slidr.render.seaborn import render_seaborn_svg

    svg = render_seaborn_svg(elem.content)
    if not svg:
        return _render_fallback_text(elem, ctx, GraphicStyleRegistry(),
                                     TextStyleRegistry(), odp)

    # Write SVG to temp file for add_file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(svg)
        tmp_path = f.name
    uri = odp.add_file(tmp_path)
    os.unlink(tmp_path)

    # Extract dimensions from SVG viewBox
    size_cm = _svg_dims(svg)
    if size_cm[0] > ctx.width * 0.9:
        scale = (ctx.width * 0.9) / size_cm[0]
        size_cm = (ctx.width * 0.9, size_cm[1] * scale)
    height = size_cm[1]
    frame = Frame.image_frame(
        image=uri,
        text="",
        size=(f"{size_cm[0]:.2f}cm", f"{size_cm[1]:.2f}cm"),
        position=(
            f"{ctx.x + (ctx.width - size_cm[0]) / 2:.2f}cm",
            f"{ctx.y:.2f}cm",
        ),
        anchor_type="page",
    )
    ctx.y += height + ctx.gap
    return [frame]


def _normalize_svg(svg: str) -> str:
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


def _svg_dims(svg: str) -> tuple[float, float]:
    """Extract SVG dimensions. For viewBox-based SVGs, use aspect ratio.
    Fallback to (16, 9) cm."""
    import re
    vb = re.search(r'viewBox="[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)"', svg)
    if vb:
        vb_w, vb_h = float(vb.group(1)), float(vb.group(2))
    else:
        return (16.0, 9.0)
    # If width=100%, use viewBox aspect ratio with a fixed width
    has_pct_width = 'width="100%"' in svg
    if has_pct_width:
        target_w = 20.0  # cm
        target_h = target_w * (vb_h / vb_w) if vb_w else target_w
        return (target_w, target_h)
    return (vb_w * 0.0353, vb_h * 0.0353)  # pt -> cm


def _render_mermaid_odp(
    elem: Elem, ctx: LayoutContext, odp: Document
) -> list[Element]:
    try:
        from mmdc import render as render_mmd

        d = render_mmd(elem.content)
        svg = d.svg()

        svg = _normalize_svg(svg)
        with tempfile.NamedTemporaryFile(
            suffix=".svg", mode="w", delete=False
        ) as f:
            f.write(svg)
            tmp_path = f.name
        uri = odp.add_file(tmp_path)
        os.unlink(tmp_path)

        size_cm = _svg_dims(svg)
        if size_cm[0] > ctx.width * 0.9:
            scale = (ctx.width * 0.9) / size_cm[0]
            size_cm = (ctx.width * 0.9, size_cm[1] * scale)
        height = size_cm[1]
        frame = Frame.image_frame(
            image=uri,
            text="",
            size=(f"{size_cm[0]:.2f}cm", f"{size_cm[1]:.2f}cm"),
            position=(
                f"{ctx.x + (ctx.width - size_cm[0]) / 2:.2f}cm",
                f"{ctx.y:.2f}cm",
            ),
            anchor_type="page",
        )
        ctx.y += height + ctx.gap
        return [frame]
    except Exception:
        return _render_fallback_text(elem, ctx, GraphicStyleRegistry(),
                                     TextStyleRegistry(), odp)


def _render_text(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    if elem.kind == "code" and elem.language == "seaborn":
        return _render_seaborn_odp(elem, ctx, odp)
    if elem.kind == "code" and elem.language == "mermaid":
        return _render_mermaid_odp(elem, ctx, odp)
    if not elem.inlines:
        return []
    if _is_image_elem(elem):
        return _render_image(elem, ctx, gr, tr, odp)
    if not elem.text.strip():
        return []
    key = _style_key_for(elem)
    gname = gr.register(key)
    height = _estimate_text_height(elem.text, elem.font_size, ctx.width)
    p = _build_paragraph(elem.inlines, tr)
    frame = Frame.text_frame(
        p,
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]


def _render_speaker(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    name = elem.attrs.get("name", "")
    role = elem.attrs.get("role", "")
    frame_key = StyleKey(
        font_size=20,
        color=elem.color,
        font_weight="normal",
        font_style="normal",
        font_family="Liberation Sans",
        fill="",
        text_align="left",
        padding="0cm",
    )
    fname = gr.register(frame_key)
    p = Paragraph()
    p.append(Span(name, style=tr.register(TextStyleKey(weight="bold"))))
    if role:
        p.append("\n")
        p.append(
            Span(role, style=tr.register(TextStyleKey(font_style="italic")))
        )
    height = 2.5 if role else 1.5
    frame = Frame.text_frame(
        p,
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=fname,
    )
    ctx.y += height + ctx.gap
    return [frame]


def _render_list(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    from odfdo import List as OdfList, ListItem

    key = StyleKey(
        font_size=elem.font_size,
        color=elem.color,
        font_weight="normal",
        font_style="normal",
        font_family="Liberation Sans",
        fill="",
        text_align="left",
        padding="0cm",
    )
    gname = gr.register(key)

    lst = OdfList()
    for i, item_text in enumerate(elem.items):
        li = ListItem()
        if i < len(elem.item_inlines):
            p = _build_paragraph(elem.item_inlines[i], tr)
        else:
            p = Paragraph(item_text)
        li.append(p)
        lst.append(li)

    height = len(elem.items) * 1.0 + 0.5  # rough estimate
    frame = Frame.text_frame(
        lst,
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]


def _render_table(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    nrows = len(elem.rows) + 1
    ncols = len(elem.headers)
    t = Table(f"table_{_next_table_id()}", width=ncols, height=nrows)
    bold_name = tr.register(TextStyleKey(weight="bold"))
    for j, h in enumerate(elem.headers):
        t.set_value((0, j), h)
        cell = t.get_cell((0, j))
        if cell is not None:
            p = cell.get_element("text:p")
            if p is not None:
                p.clear()
                p.append(Span(h, style=bold_name))
    for i, row in enumerate(elem.rows):
        for j, cell_text in enumerate(row):
            t.set_value((i + 1, j), cell_text)
    gname = gr.register(
        StyleKey(
            font_size=elem.font_size,
            color=elem.color,
            font_weight="normal",
            font_style="normal",
            font_family="Liberation Sans",
            fill="",
            text_align="left",
            padding="0.2cm",
        )
    )
    t.style = gname
    height = 0.6 * nrows
    ctx.y += height + ctx.gap
    return [t]


def _render_grid(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    cols = elem.cols or len(elem.children) or 2
    if cols <= 0:
        cols = 1
    col_w = (ctx.width - ctx.gap * (cols - 1)) / cols
    cell_est = []
    for child in elem.children:
        cell_est.append(_estimate_elem_height(child, col_w))
    row_h = max(cell_est) if cell_est else 0.0
    frames: list[Element] = []
    start_y = ctx.y
    for i, child in enumerate(elem.children):
        col_x = ctx.x + i * (col_w + ctx.gap)
        child_ctx = _child_ctx(ctx, x=col_x, y=start_y, width=col_w)
        child_frames = _render_elem(child, child_ctx, gr, tr, odp)
        frames.extend(child_frames)
    ctx.y = start_y + row_h + ctx.gap
    return frames


def _render_card(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    fill_color = _tag_to_color(elem.tag or "")
    key = StyleKey(
        font_size=18,
        color="#333333",
        font_weight="normal",
        font_style="normal",
        font_family="Liberation Sans",
        fill=fill_color,
        text_align="left",
        padding="0.5cm",
    )
    gname = gr.register(key)
    paragraphs: list[Element] = []
    if elem.header:
        p = Paragraph()
        p.append(
            Span(elem.header, style=tr.register(TextStyleKey(weight="bold")))
        )
        paragraphs.append(p)
    for line in elem.body:
        paragraphs.append(Paragraph(line))
    total_lines = (1 if elem.header else 0) + len(elem.body) + 1
    height_cm = total_lines * 1.2
    frame = Frame.text_frame(
        paragraphs,
        size=(f"{ctx.width:.2f}cm", f"{height_cm:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += height_cm + ctx.gap
    return [frame]


# ---------------------------------------------------------------------------
# Dispatch + entry point
# ---------------------------------------------------------------------------

_RENDERERS: dict[str, Any] = {
    "heading": _render_text,
    "text": _render_text,
    "quote": _render_text,
    "code": _render_text,
    "kicker": _render_text,
    "subtitle": _render_text,
    "tiny": _render_text,
    "speaker": _render_speaker,
    "list": _render_list,
    "table": _render_table,
    "grid": _render_grid,
    "card": _render_card,
}


def _render_elem(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    method = _RENDERERS.get(elem.kind, _render_text)
    return method(elem, ctx, gr, tr, odp)


def _make_logo_frame(uri: str, page_w: float, page_h: float) -> Frame:
    logo_w = 3.0
    logo_h = 1.3
    right_margin = 1.0
    top_margin = 1.0
    frame = Frame.image_frame(
        image=uri,
        text="",
        size=(f"{logo_w:.2f}cm", f"{logo_h:.2f}cm"),
        position=(
            f"{page_w - logo_w - right_margin:.2f}cm",
            f"{top_margin:.2f}cm",
        ),
        anchor_type="page",
    )
    frame.svg_title = "Logo"
    return frame


def render(
    doc: ASTDocument,
    output_path: Path,
    base_css: str = "",
    theme_css: str = "",
    page_width: float = 28.0,
    page_height: float = 15.75,
    margin: float = 2.0,
    source_dir: Path | None = None,
) -> None:
    """Render Document AST to an ODP file.

    source_dir: markdown file's parent directory, for resolving relative image paths.
    """
    slides = build_ir(doc, base_css, theme_css)
    odp = Document("presentation")
    odp.body.clear()

    logo_uri = None
    logo_path = doc.meta.logo
    if logo_path and source_dir:
        logo_path = str((source_dir / logo_path).resolve())
    if logo_path and os.path.isfile(logo_path):
        logo_uri = odp.add_file(logo_path)

    gr = GraphicStyleRegistry()
    tr = TextStyleRegistry()

    ctx = LayoutContext(
        x=margin,
        y=margin,
        width=page_width - 2 * margin,
        page_width=page_width,
        page_height=page_height,
        margin_left=margin,
        margin_top=margin,
        gap=0.5,
        source_dir=source_dir,
    )

    for i, slide in enumerate(slides):
        page = DrawPage(f"slide{i + 1}", name=f"Slide {i + 1}")
        slide_ctx = _child_ctx(ctx, y=margin, x=margin, width=ctx.width)

        for elem in slide.elements:
            frames = _render_elem(elem, slide_ctx, gr, tr, odp)
            for f in frames:
                page.append(f)

        if logo_uri:
            page.append(_make_logo_frame(logo_uri, page_width, page_height))

        odp.body.append(page)

    gr.insert_all(odp)
    tr.insert_all(odp)
    odp.save(str(output_path), pretty=True)
