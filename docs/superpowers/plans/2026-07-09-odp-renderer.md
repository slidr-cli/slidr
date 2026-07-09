# ODP Renderer Implementation Plan

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** Add ODP output to Slidr via odfdo, consuming the SlideIR intermediate representation.

**架构：** Single new file `src/slidr/render/odp.py` with style registries, layout engine, and element renderers. Small IR changes: add `inlines` and `item_inlines` fields to `Elem`. CLI gets `--odp` flag.

**技术栈：** odfdo, Python dataclasses, the existing ir.py/build_ir pipeline

---

### Task 1: IR changes -- add inline fields to Elem

**File:**
- 修改：`src/slidr/render/ir.py`

- [ ] **步骤 1：Add `inlines` and `item_inlines` fields to Elem dataclass**

```python
@dataclass
class Elem:
    kind: str
    content: str | list[Any] = ""
    text: str = ""
    font_size: int = 18
    font_weight: str = "normal"
    color: str = "#333"
    bg: str = ""
    accent: str = "#0288d1"
    muted: str = "#777"
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
```

- [ ] **步骤 2：Set `inlines` in `_convert_node` for nodes with inline content**

In `_convert_node`, for Heading:
```python
if isinstance(node, Heading):
    fs = {1: styles.get("font_h1", 44), 2: styles.get("font_h2", 32), 3: styles.get("font_h3", 18)}.get(node.level, 18)
    return Elem(kind="heading", content=_render_inline_html(node.content),
                text=_render_inline_text(node.content),
                inlines=node.content,
                level=node.level, font_size=fs, color=base.color)
```

For Paragraph:
```python
elif isinstance(node, Paragraph):
    return Elem(kind="text", content=_render_inline_html(node.content),
                text=_render_inline_text(node.content),
                inlines=node.content,
                font_size=base.font_size, color=base.color)
```

For Quote:
```python
elif isinstance(node, Quote):
    fs = styles.get("font_quote", 24)
    return Elem(kind="quote", content=_render_inline_html(node.content),
                text=_render_inline_text(node.content),
                inlines=node.content,
                font_size=fs, color=base.muted, accent=base.accent)
```

For ListNode:
```python
elif isinstance(node, ListNode):
    items_html = [_render_inline_html(item) for item in node.items]
    items_text = [_render_inline_text(item) for item in node.items]
    fs = styles.get("font_li", 16)
    return Elem(kind="list", content=items_html, text=">".join(items_text),
                items=items_text, inlines=node.content if hasattr(node, 'content') else [],
                item_inlines=[list(item) for item in node.items],
                font_size=fs, color=base.color)
```

- [ ] **步骤 3：Run existing tests to verify no regression**

```bash
pdm run pytest
```

- [ ] **步骤 4：Commit**

```bash
git add src/slidr/render/ir.py
git commit -m "feat(ir): add inlines and item_inlines fields to Elem for ODP rendering"
```

---

### Task 2: ODP renderer -- registries and layout context

**File:**
- 创建：`src/slidr/render/odp.py`

- [ ] **步骤 1：Create file with imports and dataclasses**

```python
"""ODP renderer consuming SlideIR."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from itertools import count
from pathlib import Path
from typing import Any

from odfdo import (
    Document, DrawPage, Frame, Paragraph, Span, Style, Table,
)
from odfdo.element import Element

from slidr.parser.ast import Document as ASTDocument, Image
from slidr.render.ir import build_ir, SlideIR, Elem


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
```

- [ ] **步骤 2：Add GraphicStyleRegistry and TextStyleRegistry**

```python
class GraphicStyleRegistry:
    def __init__(self):
        self._styles: dict[StyleKey, str] = {}
        self._counter = count(1)

    def register(self, key: StyleKey) -> str:
        if key not in self._styles:
            self._styles[key] = f"SlidrG_{next(self._counter):03d}"
        return self._styles[key]

    def insert_all(self, document: Document) -> None:
        for key, name in self._styles.items():
            style = Style(
                "graphic",
                name=name,
                parent="standard",
                stroke="none",
                fill_color=key.fill if key.fill else "none",
                padding_top=key.padding,
                padding_bottom=key.padding,
                padding_left=key.padding,
                padding_right=key.padding,
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
    def __init__(self):
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
```

- [ ] **步骤 3：Add helpers**

```python
def _child_ctx(parent: LayoutContext, **overrides) -> LayoutContext:
    return replace(parent, **overrides)


_table_seq = count(1)


def _next_table_id() -> int:
    return next(_table_seq)


_TAG_COLORS = {
    "green": "#e8f5e9", "red": "#ffebee", "blue": "#e3f2fd",
    "yellow": "#fff9c4", "orange": "#fff3e0", "purple": "#f3e5f5",
    "": "#f5f5f5",
}


def _tag_to_color(tag: str) -> str:
    return _TAG_COLORS.get(tag, "#f5f5f5")
```

- [ ] **步骤 4：Commit**

```bash
git add src/slidr/render/odp.py
git commit -m "feat(odp): add style registries and layout context"
```

---

### Task 3: ODP renderer -- text element rendering

**File:**
- 修改：`src/slidr/render/odp.py`

- [ ] **步骤 1：Add `_style_key_for` and `_build_paragraph` utilities**

```python
def _style_key_for(elem: Elem) -> StyleKey:
    family = "Liberation Mono" if elem.kind == "code" else "Liberation Sans"
    weight = "bold" if elem.kind in ("heading", "kicker") else "normal"
    fstyle = "italic" if elem.kind == "quote" else "normal"
    align = "center" if elem.kind == "subtitle" else "left"
    color = elem.color
    if elem.kind in ("quote", "subtitle", "tiny"):
        color = elem.muted
    return StyleKey(
        font_size=elem.font_size, color=color,
        font_weight=weight, font_style=fstyle,
        font_family=family, fill="", text_align=align, padding="0cm",
    )


def _build_paragraph(inlines: list, tr: TextStyleRegistry) -> Paragraph:
    from slidr.parser.ast import (
        Text, Strong, Emphasis, Strikethrough, CodeSpan, SoftBreak,
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
    from slidr.parser.ast import Text, Strong, Emphasis, Strikethrough, CodeSpan
    result = []
    for child in children:
        if isinstance(child, Text):
            result.append(child.content)
        elif isinstance(child, (Strong, Emphasis, Strikethrough)):
            result.extend(_walk_text_children(child.children))
        elif isinstance(child, CodeSpan):
            result.append(child.content)
    return result
```

- [ ] **步骤 2：Add `_is_image_elem`, `_render_image`, `_render_text`**

```python
def _is_image_elem(elem: Elem) -> bool:
    from slidr.parser.ast import Image as ASTImage
    return (
        elem.kind == "text"
        and len(elem.inlines) == 1
        and isinstance(elem.inlines[0], ASTImage)
    )


def _render_image(elem: Elem, ctx: LayoutContext, odp: Document) -> list[Element]:
    from slidr.parser.ast import Image as ASTImage
    img = elem.inlines[0]
    if not img.src or not os.path.isfile(img.src):
        return _render_text(elem, ctx, GraphicStyleRegistry(), TextStyleRegistry(), odp)
    uri = odp.add_file(img.src)
    size_cm = _image_natural_size(img.src)
    if size_cm[0] > ctx.width:
        scale = ctx.width / size_cm[0]
        size_cm = (ctx.width, size_cm[1] * scale)
    height = size_cm[1]
    frame = Frame.image_frame(
        image=uri,
        text=img.title or "",
        size=(f"{size_cm[0]:.2f}cm", f"{size_cm[1]:.2f}cm"),
        position=(f"{ctx.x + (ctx.width - size_cm[0]) / 2:.2f}cm",
                  f"{ctx.y:.2f}cm"),
        anchor_type="page",
    )
    if img.title:
        frame.svg_title = img.title
    if img.alt:
        frame.svg_description = img.alt
    ctx.y += height + ctx.gap
    return [frame]


def _image_natural_size(path: str) -> tuple[float, float]:
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w_px, h_px = im.size
        return (w_px * 2.54 / 72, h_px * 2.54 / 72)
    except Exception:
        return (16.0, 9.0)


def _estimate_text_height(text: str, font_size: int, width_cm: float) -> float:
    if not text:
        return 0.0
    width_pt = width_cm / 0.0353
    char_width_pt = font_size * 0.5
    chars_per_line = max(1, int(width_pt / char_width_pt))
    lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
    line_height_pt = font_size * 1.4
    return (lines * line_height_pt) * 0.0353


def _render_text(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    if not elem.inlines:
        return []
    if _is_image_elem(elem):
        return _render_image(elem, ctx, odp)
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
```

- [ ] **步骤 3：Commit**

```bash
git add src/slidr/render/odp.py
git commit -m "feat(odp): add text/image element rendering"
```

---

### Task 4: ODP renderer -- speaker, list, table, grid, card rendering

**File:**
- 修改：`src/slidr/render/odp.py`

- [ ] **步骤 1：Add `_render_speaker`, `_render_list`**

```python
def _render_speaker(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    name = elem.attrs.get("name", "")
    role = elem.attrs.get("role", "")
    frame_key = StyleKey(
        font_size=20, color=elem.color, font_weight="normal",
        font_style="normal", font_family="Liberation Sans",
        fill="", text_align="left", padding="0cm",
    )
    fname = gr.register(frame_key)
    p = Paragraph()
    p.append(Span(name, style=tr.register(TextStyleKey(weight="bold"))))
    if role:
        p.append("\n")
        p.append(Span(role, style=tr.register(TextStyleKey(font_style="italic"))))
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
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    key = StyleKey(
        font_size=elem.font_size, color=elem.color,
        font_weight="normal", font_style="normal",
        font_family="Liberation Sans", fill="",
        text_align="left", padding="0cm",
    )
    gname = gr.register(key)
    frames = []
    indent_cm = 0.8
    for i, item_text in enumerate(elem.items):
        if i < len(elem.item_inlines):
            p = _build_paragraph(elem.item_inlines[i], tr)
            p.insert(0, "\u2022  ")
        else:
            p = Paragraph(f"\u2022  {item_text}")
        h = _estimate_text_height(item_text, elem.font_size, ctx.width - indent_cm)
        frame = Frame.text_frame(
            p,
            size=(f"{ctx.width - indent_cm:.2f}cm", f"{h:.2f}cm"),
            position=(f"{ctx.x + indent_cm:.2f}cm", f"{ctx.y:.2f}cm"),
            style=gname,
        )
        frames.append(frame)
        ctx.y += h + 0.2
    ctx.y += ctx.gap
    return frames
```

- [ ] **步骤 2：Add `_render_table`, `_render_grid`**

```python
def _render_table(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    nrows = len(elem.rows) + 1
    ncols = len(elem.headers)
    t = Table(f"table_{_next_table_id()}", width=ncols, height=nrows)
    bold_name = tr.register(TextStyleKey(weight="bold"))
    for j, h in enumerate(elem.headers):
        cell = t.set_value((0, j), h)
        p = cell.get_element("text:p")
        if p is not None:
            p.clear()
            p.append(Span(h, style=bold_name))
    for i, row in enumerate(elem.rows):
        for j, cell_text in enumerate(row):
            t.set_value((i + 1, j), cell_text)
    gname = gr.register(StyleKey(
        font_size=elem.font_size, color=elem.color,
        font_weight="normal", font_style="normal",
        font_family="Liberation Sans", fill="",
        text_align="left", padding="0.2cm",
    ))
    t.style = gname
    height = 0.6 * nrows
    ctx.y += height + ctx.gap
    return [t]


def _estimate_elem_height(elem: Elem, width_cm: float) -> float:
    kind = elem.kind
    if kind in ("heading", "text", "quote", "code", "kicker", "subtitle", "tiny"):
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


def _render_grid(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    cols = elem.cols or len(elem.children) or 2
    if cols <= 0:
        cols = 1
    col_w = (ctx.width - ctx.gap * (cols - 1)) / cols
    cell_est = []
    for child in elem.children:
        cell_est.append(_estimate_elem_height(child, col_w))
    row_h = max(cell_est) if cell_est else 0.0
    frames = []
    start_y = ctx.y
    for i, child in enumerate(elem.children):
        col_x = ctx.x + i * (col_w + ctx.gap)
        child_ctx = _child_ctx(ctx, x=col_x, y=start_y, width=col_w)
        child_frames = _render_elem(child, child_ctx, gr, tr, odp)
        frames.extend(child_frames)
    ctx.y = start_y + row_h + ctx.gap
    return frames
```

- [ ] **步骤 3：Add `_render_card`**

```python
def _render_card(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    fill_color = _tag_to_color(elem.tag or "")
    key = StyleKey(
        font_size=18, color="#333333",
        font_weight="normal", font_style="normal",
        font_family="Liberation Sans", fill=fill_color,
        text_align="left", padding="0.5cm",
    )
    gname = gr.register(key)
    paragraphs = []
    if elem.header:
        p = Paragraph()
        p.append(Span(elem.header, style=tr.register(TextStyleKey(weight="bold"))))
        paragraphs.append(p)
    for line in elem.body:
        paragraphs.append(Paragraph(line))
    total_lines = (1 if elem.header else 0) + len(elem.body) + 1
    height = total_lines * 1.2
    frame = Frame.text_frame(
        paragraphs,
        size=(f"{ctx.width:.2f}cm", f"{height:.2f}cm"),
        position=(f"{ctx.x:.2f}cm", f"{ctx.y:.2f}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]
```

- [ ] **步骤 4：Commit**

```bash
git add src/slidr/render/odp.py
git commit -m "feat(odp): add speaker, list, table, grid, card rendering"
```

---

### Task 5: ODP renderer -- dispatch, entry point, logo

**File:**
- 修改：`src/slidr/render/odp.py`

- [ ] **步骤 1：Add `_render_elem` dispatch and `render` entry point**

```python
def _render_elem(
    elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
    tr: TextStyleRegistry, odp: Document,
) -> list[Element]:
    method = {
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
    }.get(elem.kind, _render_text)
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
        position=(f"{page_w - logo_w - right_margin:.2f}cm",
                  f"{top_margin:.2f}cm"),
        anchor_type="page",
    )
    frame.svg_title = "Logo"
    return frame


def render(
    doc: ASTDocument, output_path: Path, base_css: str = "",
    theme_css: str = "", page_width: float = 28.0,
    page_height: float = 15.75, margin: float = 2.0,
) -> None:
    """Render Document AST to an ODP file."""
    slides = build_ir(doc, base_css, theme_css)
    odp = Document("presentation")
    odp.body.clear()

    logo_uri = None
    if doc.meta.logo and os.path.isfile(doc.meta.logo):
        logo_uri = odp.add_file(doc.meta.logo)

    gr = GraphicStyleRegistry()
    tr = TextStyleRegistry()

    ctx = LayoutContext(
        x=margin, y=margin,
        width=page_width - 2 * margin,
        page_width=page_width, page_height=page_height,
        margin_left=margin, margin_top=margin,
        gap=0.5,
    )

    for i, slide in enumerate(slides):
        page = DrawPage(f"slide{i+1}", name=f"Slide {i+1}")
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
```

- [ ] **步骤 2：Commit**

```bash
git add src/slidr/render/odp.py
git commit -m "feat(odp): add dispatch, entry point, logo overlay"
```

---

### Task 6: CLI integration

**File:**
- 修改：`src/slidr/cli.py`

- [ ] **步骤 1：Add import and --odp option**

```python
from slidr.render.odp import render as render_odp
```

Add `odp` parameter to callback:
```python
odp: bool = typer.Option(False, "--odp", help="Generate ODP"),
```

- [ ] **步骤 2：Add ODP rendering block**

After the pptx block, add:
```python
    if odp:
        odp_path = out_dir / f"{stem}.odp"
        render_odp(doc, odp_path, base_css(), default_theme() + "\n" + (doc.meta.style or ""))
        typer.echo(f"Wrote {odp_path} ({odp_path.stat().st_size} bytes)")
        return
```

- [ ] **步骤 3：Run tests**

```bash
pdm run pytest
```

- [ ] **步骤 4：Commit**

```bash
git add src/slidr/cli.py
git commit -m "feat(cli): add --odp flag for ODP output"
```

---

### Task 7: End-to-end smoke test

- [ ] **步骤 1：Create a test markdown file**

```bash
cat > /tmp/test_odp.md << 'EOF'
---
title: Test ODP Output
---

# Title Slide
@kicker Testing ODP
@speaker name=Dev Team role=Engineers

---

## Rich Text
This is **bold** and *italic* and `code` and ~~strikethrough~~.

---

::: grid
::: card {tag=green}
Card One
Body text
:::
::: card {tag=blue}
Card Two
Body text
:::
:::

---

| Header | Value |
|--------|-------|
| Foo    | 42    |
| Bar    | 99    |

---

- Item one
- Item two
- Item three
EOF
```

- [ ] **步骤 2：Run slidr with --odp**

```bash
pdm run slidr /tmp/test_odp.md --odp
```

- [ ] **步骤 3：Verify output**

```bash
ls -la /tmp/test_odp/dist/test_odp.odp
ls -la /tmp/test_odp/dist/test_odp.html
```

Check that ODP file is non-empty and valid:
```bash
pdm run python -c "
from odfdo import Document
doc = Document('/tmp/test_odp/dist/test_odp.odp')
print(f'Type: {doc.get_type()}')
print(f'Slides: {len(doc.body.get_draw_pages())}')
for page in doc.body.get_draw_pages():
    print(f'  {page.name}: {len(page.children)} children')
"
```

Expected: 5 slides, each with children. Type is "presentation".
