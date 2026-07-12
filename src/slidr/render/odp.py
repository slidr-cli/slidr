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

# Import from refactored modules
from slidr.render.odf.style import (
    StyleKey, TextStyleKey, GraphicStyleRegistry, TextStyleRegistry,
    set_fonts, set_border_radius, set_border_color, set_tag_colors,
    tag_fill, tag_border, _TEXT_ALIGN, _FONT_SANS, _FONT_MONO,
    _BORDER_RADIUS, _BORDER_COLOR, _FONT_SCALE,
    create_table_styles,
)
from slidr.render.odf.layout import (
    LayoutContext, child_ctx,
    estimate_text_height, estimate_elem_height,
)


# Keep module globals here for now (used by _style_key_for et al)

_TEXT_ALIGN = _TEXT_ALIGN
_TABLE_CELL_STYLE = ""  # redirect from style module
_TEXT_ALIGN = "left"
_FONT_H1 = 63
_FONT_H2 = 36
_FONT_H3 = 18
_FONT_BODY = 18
_FONT_CODE = 14
_FONT_QUOTE = 24
_FONT_LIST = 16
_FONT_KICKER = 14
_FONT_SUBTITLE = 32
_FONT_SPEAKER = 18
_FONT_TINY = 13


def set_fonts(sans: str, mono: str) -> None:
    global _FONT_SANS, _FONT_MONO
    _FONT_SANS = sans
    _FONT_MONO = mono


def set_border_radius(radius: str) -> None:
    global _BORDER_RADIUS
    _BORDER_RADIUS = radius


def set_border_color(color: str) -> None:
    global _BORDER_COLOR
    _BORDER_COLOR = color


def _em_to_cm(value: str) -> str:
    """Convert CSS em value to cm for ODP. Falls back to input if not em."""
    if value.endswith("em"):
        return f"{float(value[:-2]) * 0.35:.3f}cm"
    return value


@dataclass(frozen=True)
class StyleKey:
    font_size: int = 0
    color: str = ""
    font_weight: str = ""
    font_style: str = ""
    font_family: str = ""
    fill: str = ""
    text_align: str = ""
    padding: str = ""
    border_radius: str = ""
    border_color: str = ""
    border_width: str = ""


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
    min_height: float = 0.0


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
            else:
                kwargs["draw:fill"] = "none"
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
            if key.border_radius:
                props = style.get_element("style:graphic-properties")
                if props is not None:
                    props.set_attribute("draw:corner-radius", key.border_radius)
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


_PARA_COUNTER = count(1)
_PARA_STYLES: dict[StyleKey, str] = {}


def _register_paragraph_style(key: StyleKey, gr: GraphicStyleRegistry,
                               document: Document) -> str:
    """Register a paragraph-level text style for per-paragraph font differences."""
    global _PARA_STYLES
    if key not in _PARA_STYLES:
        _PARA_STYLES[key] = f"SlidrP_{next(_PARA_COUNTER):03d}"
        gr.register(key)  # also register as graphic style for the frame fallback
    return _PARA_STYLES[key]


def _override_template_defaults(document: Document, align: str) -> None:
    """Override ODP template paragraph defaults to match CSS section text-align."""
    for style in document.get_styles(family="paragraph"):
        props = style.get_properties()
        if props and "fo:text-align" in props and props["fo:text-align"] != align:
            style.set_properties(area="paragraph", text_align=align)


def _swap_elem_colors(elements: list[Elem], dark: dict) -> None:
    """Swap element colors to dark mode values."""
    ink = dark.get("ink_rgb_hex", "#e0e0e0")
    muted = dark.get("muted_rgb_hex", "#999")
    accent = dark.get("accent_rgb_hex", "#4fc3f7")
    for e in elements:
        if e.color and e.color != muted:
            e.color = ink
        e.muted = muted
        e.accent = accent
        _swap_elem_colors(e.children, dark)


def _set_page_dims(document: Document, w_cm: float, h_cm: float) -> None:
    """Set the page-layout dimensions to the requested size."""
    layout = document.get_style("page-layout", "PM1")
    if layout is not None:
        props = layout.get_element("style:page-layout-properties")
        if props is not None:
            props.set_attribute("fo:page-width", f"{w_cm:.2f}cm")
            props.set_attribute("fo:page-height", f"{h_cm:.2f}cm")


def _create_dark_master(document: Document, bg_color: str) -> None:
    """Clone the default master page with a dark background."""
    master = document.get_style("master-page", "presentation")
    if master is None:
        return
    dark_master = master.clone
    dark_master.name = "SlidrDark"
    dark_master.display_name = "Slidr Dark"
    # Set background on the master page's draw page
    draw_page = dark_master.get_element("draw:page")
    if draw_page is not None:
        bg = draw_page.get_element("draw:rect") or draw_page.get_element("draw:frame")
        if bg is not None:
            bg.set_attribute("draw:fill", "solid")
            bg.set_attribute("draw:fill-color", bg_color)
    document.insert_style(dark_master)


def _apply_border_radius(frame: Frame, radius: str) -> None:
    """Set draw:corner-radius directly on the frame element."""
    if radius:
        frame.set_attribute("draw:corner-radius", _em_to_cm(radius))


def _apply_card_border(frame: Frame, color: str = "") -> None:
    """Apply thin continuous border matching CSS --card-border to a frame."""
    frame.set_attribute("draw:stroke", "solid")
    frame.set_attribute("svg:stroke-color", color or _BORDER_COLOR)
    frame.set_attribute("svg:stroke-width", "0.01mm")


def _child_ctx(parent: LayoutContext, **overrides: Any) -> LayoutContext:
    return replace(parent, **overrides)
    return replace(parent, **overrides)


_table_seq = count(1)


def _next_table_id() -> int:
    return next(_table_seq)


_TAG_COLORS: dict[str, str] = {}
_TAG_BORDERS: dict[str, str] = {}


def set_tag_colors(colors: dict[str, tuple[str, str]]) -> None:
    global _TAG_COLORS, _TAG_BORDERS
    _TAG_COLORS = {tag: fill for tag, (fill, _) in colors.items()}
    _TAG_BORDERS = {tag: border for tag, (_, border) in colors.items()}
    if "" not in _TAG_COLORS:
        _TAG_COLORS[""] = _TAG_COLORS.get("blue", "#e3f2fd")


def _tag_to_color(tag: str) -> str:
    return _TAG_COLORS.get(tag, _TAG_COLORS.get("", "#e3f2fd"))


def _tag_border(tag: str) -> str:
    return _TAG_BORDERS.get(tag, _BORDER_COLOR)


# ---------------------------------------------------------------------------
# Style key factory
# ---------------------------------------------------------------------------


def _style_key_for(elem: Elem) -> StyleKey:
    family = _FONT_MONO if elem.kind == "code" else _FONT_SANS
    weight = "bold" if elem.kind in ("heading", "kicker") else "normal"
    fstyle = "italic" if elem.kind == "quote" else "normal"
    align = _TEXT_ALIGN  # set by render() per slide layout
    color = elem.color
    if elem.kind in ("quote", "subtitle", "tiny"):
        color = elem.muted
    return StyleKey(
        font_size=max(8, int(elem.font_size * _FONT_SCALE)),
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
                TextStyleKey(font_family=_FONT_MONO, font_size=14)
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
    # Count explicit newlines first, then wrap each line
    raw_lines = text.split("\n")
    total_lines = 0
    for line in raw_lines:
        if not line:
            total_lines += 1
        else:
            total_lines += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
    lines = max(1, total_lines)
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
        total_h = 0.0
        for i in range(0, len(elem.children), cols):
            row_h = 0.0
            for child in elem.children[i:i + cols]:
                row_h = max(row_h, _estimate_elem_height(child, col_w))
            total_h += row_h
        return total_h + 0.5
    elif kind == "card":
        h = 1.0 if elem.header else 0.0
        for line in elem.body:
            h += max(0.5, _estimate_text_height(line, elem.font_size or 18, width_cm)) + 0.2
        return h + 0.5
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


def _render_svg_odp(
    elem: Elem, ctx: LayoutContext, odp: Document
) -> list[Element]:
    """Render an SVG or PDF from the IR as an embedded image frame."""
    import tempfile

    if elem.language == "mermaid" and elem.pdf:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(elem.pdf)
            tmp_path = f.name
        uri = odp.add_file(tmp_path)
        os.unlink(tmp_path)
        size_cm = (20.0, 13.0)  # PDF dimensions are approximate
    elif elem.svg:
        with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
            f.write(elem.svg)
            tmp_path = f.name
        uri = odp.add_file(tmp_path)
        os.unlink(tmp_path)
        size_cm = _svg_dims(elem.svg)
    else:
        return _render_fallback_text(elem, ctx, GraphicStyleRegistry(),
                                     TextStyleRegistry(), odp)

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


def _render_text(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    if elem.kind == "code" and elem.language == "seaborn":
        return _render_svg_odp(elem, ctx, odp)
    if elem.kind == "code" and elem.language == "mermaid":
        return _render_svg_odp(elem, ctx, odp)
    if elem.kind == "code" and elem.language == "dot":
        return _render_svg_odp(elem, ctx, odp)
    if _is_image_elem(elem):
        return _render_image(elem, ctx, gr, tr, odp)
    if not elem.inlines and not elem.text.strip():
        return []
    key = _style_key_for(elem)
    gname = gr.register(key)
    height = _estimate_text_height(elem.text, elem.font_size, ctx.width)
    if elem.inlines:
        p = _build_paragraph(elem.inlines, tr)
    else:
        p = Paragraph(elem.text)
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
        font_family=_FONT_SANS,
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
        font_size=max(8, int(elem.font_size * _FONT_SCALE)),
        color=elem.color,
        font_weight="normal",
        font_style="normal",
        font_family=_FONT_SANS,
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

    # Header row styling
    bold_name = tr.register(TextStyleKey(weight="bold"))
    for j, h in enumerate(elem.headers):
        t.set_value((j, 0), h)
        cell = t.get_cell((j, 0))
        if cell is not None:
            p = cell.get_element("text:p")
            if p is not None:
                p.clear()
                p.append(Span(h, style=bold_name))

    for i, row in enumerate(elem.rows):
        for j, cell_text in enumerate(row):
            t.set_value((j, i + 1), cell_text)
            if _TABLE_CELL_STYLE:
                cell = t.get_cell((j, i + 1))
                if cell is not None:
                    cell.set_attribute("table:style-name", _TABLE_CELL_STYLE)

    height = 0.6 * nrows
    frame = Frame(
        name=f"table_frame_{_next_table_id()}",
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
    )
    frame.set_attribute("draw:fill", "none")
    frame.append(t)
    ctx.y += height + ctx.gap
    return [frame]


def _render_grid(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    # Column containers (col-left, col-right) stack children vertically
    if elem.layout and elem.layout.startswith("col-"):
        return _render_column(elem, ctx, gr, tr, odp)

    cols = elem.cols or len(elem.children) or 2
    if cols <= 0:
        cols = 1
    col_w = (ctx.width - ctx.gap * (cols - 1)) / cols

    # Group children into rows
    rows = []
    for i in range(0, len(elem.children), cols):
        rows.append(elem.children[i:i + cols])

    frames: list[Element] = []
    start_y = ctx.y

    for row_cells in rows:
        row_h = 0.0
        for child in row_cells:
            row_h = max(row_h, _estimate_elem_height(child, col_w))

        for i, child in enumerate(row_cells):
            col_x = ctx.x + i * (col_w + ctx.gap)
            child_ctx = _child_ctx(ctx, x=col_x, y=start_y, width=col_w, min_height=row_h)
            child_frames = _render_elem(child, child_ctx, gr, tr, odp)
            frames.extend(child_frames)

        start_y += row_h + ctx.gap

    ctx.y = start_y
    return frames


def _render_row(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    """Stack children horizontally within a row."""
    cols = len(elem.children)
    col_w = (ctx.width - ctx.gap * (cols - 1)) / cols
    frames: list[Element] = []
    max_h = 0.0
    start_y = ctx.y
    for i, child in enumerate(elem.children):
        child_ctx = _child_ctx(ctx, x=ctx.x + i * (col_w + ctx.gap), y=start_y, width=col_w)
        cf = _render_elem(child, child_ctx, gr, tr, odp)
        frames.extend(cf)
        max_h = max(max_h, child_ctx.y - start_y)
    ctx.y = start_y + max_h + ctx.gap
    return frames


def _render_column(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    """Stack children vertically within a layout column."""
    frames: list[Element] = []
    for child in elem.children:
        child_frames = _render_elem(child, ctx, gr, tr, odp)
        frames.extend(child_frames)
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
        font_family=_FONT_SANS,
        fill=fill_color,
        text_align="left",
        padding="0.5cm",
        border_radius=_BORDER_RADIUS,
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
    total_height = 0.0
    if elem.header:
        total_height += _estimate_text_height(elem.header, 20, ctx.width) + 0.3
    for line in elem.body:
        total_height += max(0.5, _estimate_text_height(line, elem.font_size or 18, ctx.width)) + 0.2
    height_cm = max(total_height + 0.5, ctx.min_height)
    frame = Frame.text_frame(
        paragraphs,
        size=(f"{ctx.width:.2f}cm", f"{height_cm:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    _apply_border_radius(frame, _BORDER_RADIUS)
    _apply_card_border(frame, _tag_border(elem.tag or ""))
    ctx.y += height_cm + ctx.gap
    return [frame]


# ---------------------------------------------------------------------------
# Block merging (combine consecutive text elements into one frame)
# ---------------------------------------------------------------------------


def _merge_text_elements(elements: list[Elem]) -> list[Elem]:
    """Merge consecutive text-like elements into block elements for single-frame rendering."""
    result = []
    buf = []
    for e in elements:
        if e.kind in ("heading", "text", "quote", "list"):
            buf.append(e)
        elif e.kind == "code" and e.language not in ("seaborn", "mermaid"):
            buf.append(e)
        elif e.kind in ("kicker", "subtitle", "speaker", "tiny"):
            # Directives keep their own style, don't merge
            if buf:
                result.append(_make_block(buf))
                buf = []
            result.append(e)
        else:
            if buf:
                result.append(_make_block(buf))
                buf = []
            result.append(e)
    if buf:
        result.append(_make_block(buf))
    return result


def _make_block(elems: list[Elem]) -> Elem:
    if len(elems) == 1:
        return elems[0]
    return Elem(kind="block", children=elems,
                font_size=elems[0].font_size, color=elems[0].color)


def _render_block(
    elem: Elem,
    ctx: LayoutContext,
    gr: GraphicStyleRegistry,
    tr: TextStyleRegistry,
    odp: Document,
) -> list[Element]:
    """Render a block of text-like elements as paragraphs in a single text frame."""
    from odfdo import List as OdfList, ListItem

    paragraphs = []
    total_height = 0.0
    for child in elem.children:
        if child.kind == "list":
            lst = OdfList()
            for i, item_text in enumerate(child.items):
                li = ListItem()
                if i < len(child.item_inlines):
                    p = _build_paragraph(child.item_inlines[i], tr)
                else:
                    p = Paragraph(item_text)
                li.append(p)
                lst.append(li)
            paragraphs.append(lst)
            total_height += len(child.items) * 1.0 + 0.3
        else:
            key = _style_key_for(child)
            # Register as paragraph style (not graphic style) for per-paragraph styling
            pname = _register_paragraph_style(key, gr, document=odp)
            if child.inlines:
                p = _build_paragraph(child.inlines, tr)
            else:
                p = Paragraph(child.text or child.content)
            p.style = pname
            paragraphs.append(p)
            total_height += _estimate_text_height(child.text, child.font_size, ctx.width) + 0.3

    key = _style_key_for(elem.children[0]) if elem.children else StyleKey()
    gname = gr.register(key)
    frame = Frame.text_frame(
        paragraphs,
        size=(f"{ctx.width:.2f}cm", f"{total_height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += total_height + ctx.gap
    return [frame]


# ---------------------------------------------------------------------------
# Dispatch + entry point
# ---------------------------------------------------------------------------

_RENDERERS: dict[str, Any] = {
    "arrow": _render_text,
    "block": _render_block,
    "heading": _render_text,
    "text": _render_text,
    "quote": _render_text,
    "code": _render_text,
    "kicker": _render_text,
    "subtitle": _render_text,
    "tiny": _render_text,
    "speaker": _render_speaker,
    "list": _render_list,
    "row": _render_row,
    "notes": _render_text,
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


def _make_logo_frame(uri: str, page_w: float, page_h: float,
                    logo_path: str = "") -> Frame:
    """Create a logo frame with correct aspect ratio from the source image."""
    target_w = 3.0  # cm, desired logo width
    target_h = 1.3  # cm, fallback if PIL unavailable
    if logo_path:
        try:
            from PIL import Image
            with Image.open(logo_path) as im:
                w_px, h_px = im.size
            target_h = target_w * (h_px / w_px) if w_px else target_h
        except Exception:
            pass
    right_margin = 1.0
    top_margin = 1.0
    frame = Frame.image_frame(
        image=uri,
        text="",
        size=(f"{target_w:.2f}cm", f"{target_h:.2f}cm"),
        position=(
            f"{page_w - target_w - right_margin:.2f}cm",
            f"{top_margin:.2f}cm",
        ),
        anchor_type="page",
    )
    frame.svg_title = "Logo"
    return frame


def _init_document(odp: Document, styles: dict, dark_styles: dict,
                   page_width: float, page_height: float,
                   px_width: int, px_height: int) -> tuple[str, str]:
    """Initialize ODP document with styles, dimensions, and masters."""
    global _BORDER_RADIUS, _BORDER_COLOR, _FONT_SCALE
    set_fonts(
        styles.get("font_body_family", "Segoe UI"),
        styles.get("font_code_family", "SFMono-Regular"),
    )
    set_border_radius(styles.get("border_radius", "0.4em"))
    set_border_color(styles.get("card_border_color", "#ddd"))
    set_tag_colors(styles.get("tag_colors", {}))

    # Table styles
    global _TABLE_CELL_STYLE
    _, _TABLE_CELL_STYLE = create_table_styles(odp, styles)

    # Font scale: ODP physical page (cm) vs HTML virtual pixels at 96dpi
    _FONT_SCALE = (page_width * 10) / (px_width / 96 * 25.4)
    global _FONT_H1, _FONT_H2, _FONT_H3, _FONT_BODY, _FONT_CODE
    global _FONT_QUOTE, _FONT_LIST, _FONT_KICKER, _FONT_SUBTITLE, _FONT_SPEAKER, _FONT_TINY
    _FONT_H1 = max(8, int(63 * _FONT_SCALE))
    _FONT_H2 = max(8, int(36 * _FONT_SCALE))
    _FONT_H3 = max(8, int(18 * _FONT_SCALE))
    _FONT_BODY = max(8, int(18 * _FONT_SCALE))
    _FONT_CODE = max(8, int(14 * _FONT_SCALE))
    _FONT_QUOTE = max(8, int(24 * _FONT_SCALE))
    _FONT_LIST = max(8, int(16 * _FONT_SCALE))
    _FONT_KICKER = max(8, int(14 * _FONT_SCALE))
    _FONT_SUBTITLE = max(8, int(32 * _FONT_SCALE))
    _FONT_SPEAKER = max(8, int(18 * _FONT_SCALE))
    _FONT_TINY = max(8, int(13 * _FONT_SCALE))

    body_align = styles.get("section_text_align", "left")
    title_align = styles.get("title_text_align", "left")
    _override_template_defaults(odp, body_align)
    _set_page_dims(odp, page_width, page_height)
    _create_dark_master(odp, dark_styles.get("ink_rgb_hex", "#1a1a2e"))

    return body_align, title_align


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
    """Render Document AST to an ODP file."""
    from slidr.render.ir import resolve_styles
    from slidr.render.seaborn import set_palette
    from slidr.theme.parser import parse_dark_theme

    set_palette(doc.meta.seaborn_theme)
    styles = resolve_styles(base_css, theme_css)
    dark_styles = parse_dark_theme(base_css, theme_css)

    slides = build_ir(doc, base_css, theme_css)
    odp = Document("presentation")
    odp.body.clear()

    dims = doc.meta.dimensions()
    _body_align, _title_align = _init_document(odp, styles, dark_styles, page_width, page_height,
                                                dims[0], dims[1])

    logo_uri = None
    logo_src = doc.meta.logo
    logo_path = logo_src
    if logo_src and source_dir:
        logo_path = str((source_dir / logo_src).resolve())
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
        global _TEXT_ALIGN, _BORDER_COLOR
        _TEXT_ALIGN = _title_align if slide.layout == "title" else _body_align

        if slide.variant == "dark":
            _BORDER_COLOR = dark_styles.get("card_border_color", "#333")
            set_tag_colors(dark_styles.get("tag_colors", {}))
            _swap_elem_colors(slide.elements, dark_styles)
            bg_color = dark_styles.get("ink_rgb_hex", "#1a1a2e")
        else:
            _BORDER_COLOR = styles.get("card_border_color", "#ddd")
            set_tag_colors(styles.get("tag_colors", {}))
            bg_color = styles.get("ink_rgb_hex", "#ffffff")
        page = DrawPage(f"slide{i + 1}", name=f"Slide {i + 1}")
        if slide.variant == "dark":
            page.master_page = "SlidrDark"
        slide_y = margin
        if slide.layout == "title":
            # Center title content vertically
            total_h = sum(_estimate_elem_height(e, ctx.width) for e in slide.elements)
            slide_y = max(margin, (page_height - total_h) / 2)
        slide_ctx = _child_ctx(ctx, y=slide_y, x=margin, width=ctx.width)

        elements = _merge_text_elements(slide.elements)
        for elem in elements:
            frames = _render_elem(elem, slide_ctx, gr, tr, odp)
            for f in frames:
                page.append(f)

        if logo_uri:
            page.append(_make_logo_frame(logo_uri, page_width, page_height, logo_path))

        odp.body.append(page)

    gr.insert_all(odp)
    tr.insert_all(odp)
    odp.save(str(output_path), pretty=True)
