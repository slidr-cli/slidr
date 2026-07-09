# ODP Renderer Design

Build ODP output from the Slidr IR, parallel to the existing PPTX renderer.

## Architecture

New file: `src/slidr/render/odp.py`. Same signature as pptx.py:

```python
def render(doc: Document, output_path: Path, base_css: str = "", theme_css: str = "") -> None
```

Pipeline: `slides.md -> parse -> AST -> build_ir -> SlideIR[] -> odp.py -> .odp`

The IR is the single source of truth. No new IR types, no changes to the parser. One field added to Elem.

## IR change

Add `inlines` field to `Elem` in `ir.py`:

```python
inlines: list[Any] = field(default_factory=list)  # raw AST Inline nodes
```

Set it in `_convert_node` for nodes with inline content (Heading, Paragraph, Quote, ListNode items):

```python
if hasattr(node, 'content'):
    elem.inlines = node.content
```

The HTML and PPTX renderers ignore this field. Zero change to existing behavior.

## Physical dimensions

Map the virtual slide (1280x720 at 96dpi) to a physical ODP page:

| Virtual  | Physical   |
|----------|------------|
| 1280px   | 28.0 cm    |
| 720px    | 15.75 cm   |
| 1px      | 0.022 cm   |

Margins: left 2.0cm, right 2.0cm, top 2.0cm. Content area: 24.0cm x 13.75cm.

Page width/height configurable via keyword args to `render()` for future non-16:9 sizes.

## Unit helpers

```python
from dataclasses import replace

def _child_ctx(parent: LayoutContext, **overrides) -> LayoutContext:
    """Clone a LayoutContext with field overrides."""
    return replace(parent, **overrides)

def _px_to_cm(px: float) -> float:
    return px * 0.022
```

## Style registries

Two registries: graphic styles (for frames) and text styles (for inline spans).

### GraphicStyleRegistry

Maps `StyleKey` -> style name. A `StyleKey` is:

```python
@dataclass(frozen=True)
class StyleKey:
    font_size: int         # pt
    color: str             # hex, e.g. "#333333"
    font_weight: str       # "normal" | "bold"
    font_style: str        # "normal" | "italic"
    font_family: str       # "Liberation Sans" | "Liberation Mono"
    fill: str              # hex or "" for transparent
    text_align: str        # "left" | "center" | "right"
    padding: str           # "0cm" | "0.5cm" etc
```

Generates odfdo `Style("graphic", ...)` objects on `insert_all(document)`:

```python
style = Style(
    "graphic",
    name=name,
    parent="standard",
    stroke="none",
    fill_color=key.fill or "none",
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
```

Style names are `"SlidrG_001"`, `"SlidrG_002"`, etc.

### TextStyleRegistry

Simpler key -- only bold, italic, monospace:

```python
@dataclass(frozen=True)
class TextStyleKey:
    weight: str = "normal"        # "normal" | "bold"
    font_style: str = "normal"    # "normal" | "italic"
    font_family: str = ""         # "" (default) | "Liberation Mono"
    font_size: int = 0            # 0 (inherit) | pt for code
```

Generates `Style("text", ...)`:

```python
Style("text", name=name, bold=(key.weight == "bold"),
      italic=(key.font_style == "italic"),
      font=key.font_family or None,
      size=f"{key.font_size}pt" if key.font_size else None)
```

Names: `"SlidrT_001"`, etc.

## Layout context

Mutable cursor tracking vertical position:

```python
@dataclass
class LayoutContext:
    x: float           # cm, current left edge
    y: float           # cm, current top edge (advances as elements render)
    width: float       # cm, available content width
    page_width: float  # cm
    page_height: float # cm
    margin_left: float # cm
    margin_top: float  # cm
    gap: float         # cm, inter-element spacing (default 0.5)
```

## Element rendering

### dispatch

All `_render_*` functions take the same signature: `(elem, ctx, gr, tr, odp)`.

```python
def _render_elem(elem: Elem, ctx: LayoutContext, gr: GraphicStyleRegistry,
                 tr: TextStyleRegistry, odp: Document) -> list[Element]:
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
```

### text / heading / quote / code / kicker / subtitle / tiny

All these render as a single text frame from inlines. The difference is the `StyleKey` they register:

```python
def _style_key_for(elem: Elem) -> StyleKey:
    family = "Liberation Mono" if elem.kind == "code" else "Liberation Sans"
    weight = "bold" if elem.kind in ("heading", "kicker") else "normal"
    style = "italic" if elem.kind == "quote" else "normal"
    align = "center" if elem.kind in ("subtitle",) else "left"
    return StyleKey(
        font_size=elem.font_size,
        color=elem.color if elem.kind not in ("quote", "subtitle", "tiny") else elem.muted,
        font_weight=weight,
        font_style=style,
        font_family=family,
        fill="",
        text_align=align,
        padding="0cm",
    )

def _render_text(elem: Elem, ctx: LayoutContext, gr, tr, odp):
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
    # Frame graphic style sets text properties. Paragraph itself gets no style.
    frame = Frame.text_frame(
        p,
        size=(f"{ctx.width}cm", f"{height}cm"),
        position=(f"{ctx.x}cm", f"{ctx.y}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]
```

### rich text paragraph builder

```python
def _build_paragraph(inlines: list, tr: TextStyleRegistry) -> Paragraph:
    p = Paragraph()
    for node in inlines:
        if isinstance(node, Text):
            p.append(node.content)
        elif isinstance(node, Strong):
            name = tr.register(TextStyleKey(weight="bold"))
            for c in _walk_text_children(node.children):
                if isinstance(c, str):
                    p.append(Span(c, style=name))
                else:
                    p.append(Span(c[1], style=tr.register(TextStyleKey(
                        weight="bold",
                        font_style=c[0] if c[0] == "italic" else "normal"))))
        elif isinstance(node, Emphasis):
            name = tr.register(TextStyleKey(font_style="italic"))
            for c in _walk_text_children(node.children):
                if isinstance(c, str):
                    p.append(Span(c, style=name))
                else:
                    p.append(Span(c[1], style=tr.register(TextStyleKey(
                        font_style="italic",
                        weight=c[0] if c[0] == "bold" else "normal"))))
        elif isinstance(node, Strikethrough):
            # ODF doesn't have strikethrough span style easily.
            # Render as plain text for now.
            text = "".join(_walk_text_children(node.children))
            p.append(text)
        elif isinstance(node, CodeSpan):
            name = tr.register(TextStyleKey(font_family="Liberation Mono", font_size=14))
            p.append(Span(node.content, style=name))
        elif isinstance(node, Image):
            # Inline images: append a placeholder string
            p.append(f" [{node.alt or 'image'}] ")
        elif isinstance(node, SoftBreak):
            p.append(" ")
    return p

def _walk_text_children(children: list) -> list:
    """Flatten inline children to a list of str and (style_flags, str) tuples."""
    result = []
    for child in children:
        if isinstance(child, Text):
            result.append(child.content)
        elif isinstance(child, (Strong, Emphasis, Strikethrough)):
            result.extend(_walk_text_children(child.children))
        elif isinstance(child, CodeSpan):
            result.append(("mono", child.content))
    return result
```

### speaker

```python
def _render_speaker(elem: Elem, ctx, gr, tr, odp):
    name = elem.attrs.get("name", "")
    role = elem.attrs.get("role", "")

    # Single graphic style for the frame; two text styles for name/role spans
    frame_key = StyleKey(font_size=20, color=elem.color, font_weight="normal",
                         font_style="normal", font_family="Liberation Sans",
                         fill="", text_align="left", padding="0cm")
    fname = gr.register(frame_key)

    name_spans = [Span(name, style=tr.register(TextStyleKey(weight="bold")))]
    if role:
        role_span_name = tr.register(TextStyleKey(font_style="italic"))
        name_spans.append("\n")
        name_spans.append(Span(role, style=role_span_name))

    p = Paragraph()
    for s in name_spans:
        p.append(s)

    height = 2.5 if role else 1.5
    frame = Frame.text_frame(
        p,
        size=(f"{ctx.width}cm", f"{height}cm"),
        position=(f"{ctx.x}cm", f"{ctx.y}cm"),
        style=fname,
    )
    ctx.y += height + ctx.gap
    return [frame]
```

### list

Each item becomes a separate text frame with a bullet prefix:

```python
def _render_list(elem: Elem, ctx, gr, tr, odp):
    key = StyleKey(font_size=elem.font_size, color=elem.color,
                   font_weight="normal", font_style="normal",
                   font_family="Liberation Sans", fill="",
                   text_align="left", padding="0cm")
    gname = gr.register(key)

    frames = []
    indent_cm = 0.8
    for i, item_text in enumerate(elem.items):
        if i < len(elem.item_inlines):
            p = _build_paragraph(elem.item_inlines[i], tr)
            p.insert(0, "\u2022  ")  # bullet as first text node before spans
        else:
            p = Paragraph(f"\u2022  {item_text}")
        h = _estimate_text_height(item_text, elem.font_size, ctx.width - indent_cm)
        frame = Frame.text_frame(
            p,
            size=(f"{ctx.width - indent_cm}cm", f"{h}cm"),
            position=(f"{ctx.x + indent_cm}cm", f"{ctx.y}cm"),
            style=gname,
        )
        frames.append(frame)
        ctx.y += h + 0.2  # tighter gap for list items

    ctx.y += ctx.gap
    return frames
```

Note: `elem.items` is a list of HTML strings (from `_render_inline_html`). The IR currently stores plain text via `_render_inline_text` joined by `>`. We need to also store per-item inlines. Add `item_inlines: list[list]` to Elem, populated in `_convert_node` for ListNode.

### table

odfdo `Table` on `DrawPage`. Header row gets bold text; a graphic style provides
cell padding. Full border and header background coloring deferred to a focused
enhancement -- the bold spans give enough visual distinction for v1.

```python
def _render_table(elem: Elem, ctx, gr, tr, odp):
    nrows = len(elem.rows) + 1
    ncols = len(elem.headers)
    t = Table(f"table_{_next_table_id()}", width=ncols, height=nrows)

    # Header row with bold
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

    # Cell padding via graphic style on the table element
    gname = gr.register(StyleKey(
        font_size=elem.font_size, color=elem.color,
        font_weight="normal", font_style="normal",
        font_family="Liberation Sans", fill="",
        text_align="left", padding="0.2cm",
    ))
    t.style = gname

    height = 0.6 * nrows  # cm
    ctx.y += height + ctx.gap
    return [t]
```

### grid

Two-pass: estimate heights, then render with aligned columns.

```python
def _render_grid(elem: Elem, ctx, gr, tr, odp):
    cols = elem.cols or len(elem.children) or 2
    if cols <= 0:
        cols = 1
    col_w = (ctx.width - ctx.gap * (cols - 1)) / cols

    # Pass 1: estimate each cell
    cell_est = []
    for child in elem.children:
        h = _estimate_elem_height(child, col_w)
        cell_est.append(h)
    row_h = max(cell_est) if cell_est else 0

    # Pass 2: render
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

### card

Text frame with fill background, containing header + body paragraphs:

```python
def _render_card(elem: Elem, ctx, gr, tr, odp):
    fill_color = _tag_to_color(elem.tag or "")
    key = StyleKey(font_size=18, color="#333333",
                   font_weight="normal", font_style="normal",
                   font_family="Liberation Sans", fill=fill_color,
                   text_align="left", padding="0.5cm")
    gname = gr.register(key)

    paragraphs = []
    if elem.header:
        p = Paragraph()
        p.append(Span(elem.header, style=tr.register(TextStyleKey(weight="bold"))))
        paragraphs.append(p)

    for line in elem.body:
        paragraphs.append(Paragraph(line))

    total_lines = (1 if elem.header else 0) + len(elem.body) + 1  # +1 padding
    height = total_lines * 1.2  # cm

    frame = Frame.text_frame(
        paragraphs,
        size=(f"{ctx.width}cm", f"{height}cm"),
        position=(f"{ctx.x}cm", f"{ctx.y}cm"),
        style=gname,
    )
    ctx.y += height + ctx.gap
    return [frame]
```

Tag color mapping:

```python
_TAG_COLORS = {
    "green": "#e8f5e9", "red": "#ffebee", "blue": "#e3f2fd",
    "yellow": "#fff9c4", "orange": "#fff3e0", "purple": "#f3e5f5",
    "": "#f5f5f5",
}

def _tag_to_color(tag: str) -> str:
    return _TAG_COLORS.get(tag, "#f5f5f5")
```

### standalone images

Images in the IR come from Paragraph nodes containing only an Image inline. The `_render_text`
function detects this before building paragraphs (see `_is_image_elem` check above).

```python
def _is_image_elem(elem: Elem) -> bool:
    return (elem.kind == "text" and len(elem.inlines) == 1
            and isinstance(elem.inlines[0], Image))

def _render_image(elem: Elem, ctx, gr, tr, odp: Document):
    img = elem.inlines[0]
    if not img.src or not os.path.isfile(img.src):
        return _render_text(elem, ctx, gr, tr, odp)

    # 1. Embed binary in ODP container, get internal URI
    uri = odp.add_file(img.src)  # returns "Pictures/<hash>.png"

    # 2. Get natural dimensions, scale to fit
    size_cm = _image_natural_size(img.src)
    if size_cm[0] > ctx.width:
        scale = ctx.width / size_cm[0]
        size_cm = (ctx.width, size_cm[1] * scale)

    # 3. Create image frame with internal URI
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
    """Get image dimensions in cm. Fallback (16, 9) cm on failure."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w_px, h_px = im.size
        return (w_px * 2.54 / 72, h_px * 2.54 / 72)
    except Exception:
        return (16.0, 9.0)
```

**Mixed inlines** (text + image + text): walk inlines, split at Image boundaries,
emit text frames for text runs and image frames for images, back to back. This is
handled by a `_render_mixed_inlines` function that segments the inline list and
renders each segment separately.

### logo overlay

Same pattern as HTML renderer: if `doc.meta.logo` is set, an image frame is placed
top-right on every slide.

```python
def render(doc: Document, output_path: Path, base_css: str = "",
           theme_css: str = "", page_width: float = 28.0,
           page_height: float = 15.75, margin: float = 2.0) -> None:
    slides = build_ir(doc, base_css, theme_css)
    odp = Document("presentation")
    odp.body.clear()

    # Pre-embed logo if set
    logo_uri = None
    if doc.meta.logo and os.path.isfile(doc.meta.logo):
        logo_uri = odp.add_file(doc.meta.logo)

    gr = GraphicStyleRegistry()
    tr = TextStyleRegistry()
    ctx = LayoutContext(...)

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


def _make_logo_frame(uri: str, page_w: float, page_h: float) -> Frame:
    """Logo frame top-right: 3cm wide, proportional height, 1cm margin."""
    logo_w = 3.0  # cm
    logo_h = 1.3   # cm (approximate, assuming ~2.3:1 aspect)
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
```

The logo dimensions are hardcoded at 3cm × 1.3cm. If the actual image has a different aspect
ratio, the frame clips. A future enhancement could read natural dimensions with PIL and scale
proportionally.

## Height estimation

```python
def _estimate_text_height(text: str, font_size: int, width_cm: float) -> float:
    """Estimate height of a text frame in cm."""
    if not text:
        return 0
    width_pt = width_cm / 0.0353  # cm -> pt
    char_width_pt = font_size * 0.5  # approximate avg char width
    chars_per_line = max(1, int(width_pt / char_width_pt))
    lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
    line_height_pt = font_size * 1.4
    return (lines * line_height_pt) * 0.0353  # pt -> cm

def _estimate_elem_height(elem: Elem, width_cm: float) -> float:
    """Estimate total height for an element (text + gap)."""
    kind = elem.kind
    if kind in ("heading", "text", "quote", "code", "kicker", "subtitle", "tiny"):
        return _estimate_text_height(elem.text, elem.font_size, width_cm) + 0.5
    elif kind == "list":
        h = 0
        for item in elem.items:
            h += _estimate_text_height(item, elem.font_size, width_cm - 0.8) + 0.2
        return h + 0.5
    elif kind == "table":
        return 0.6 * (len(elem.rows) + 1) + 0.5
    elif kind == "grid":
        cols = elem.cols or len(elem.children) or 2
        col_w = (width_cm - 0.5 * (cols - 1)) / cols
        max_h = 0
        for child in elem.children:
            max_h = max(max_h, _estimate_elem_height(child, col_w))
        return max_h + 0.5
    elif kind == "card":
        lines = (1 if elem.header else 0) + len(elem.body) + 1
        return lines * 1.2 + 0.5
    elif kind == "speaker":
        return (2.5 if elem.attrs.get("role") else 1.5) + 0.5
    return 0.5
```

## CLI integration

```python
# cli.py
from slidr.render.odp import render as render_odp

@app.callback(invoke_without_command=True)
def main(file, output_dir, pdf, pptx, odp, debug):
    ...
    if odp:
        odp_path = out_dir / f"{stem}.odp"
        render_odp(doc, odp_path, base_css(), default_theme() + "\n" + (doc.meta.style or ""))
        typer.echo(f"Wrote {odp_path} ({odp_path.stat().st_size} bytes)")
```

Add `--odp` flag:
```python
odp: bool = typer.Option(False, "--odp", help="Generate ODP")
```

## Render entry point

```python
from itertools import count

_table_seq = count(1)

def _next_table_id() -> int:
    return next(_table_seq)

def render(doc: Document, output_path: Path, base_css: str = "",
           theme_css: str = "", page_width: float = 28.0,
           page_height: float = 15.75, margin: float = 2.0) -> None:
    """Render Document AST to an ODP file."""
    slides = build_ir(doc, base_css, theme_css)

    odp = Document("presentation")
    odp.body.clear()

    # Pre-embed logo if set
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

## Element / Elem additions

One new field in `Elem`:
- `inlines: list[Any]` -- raw AST inline nodes for rich text

One new field for list items:
- `item_inlines: list[list]` -- per-item inline nodes, parallel to `items`

Set in `_convert_node`:
```python
elif isinstance(node, ListNode):
    ...
    item_inlines = [list(item) for item in node.items]
    return Elem(kind="list", ..., item_inlines=item_inlines)
```

## Edge cases

1. **Empty elements**: Skip frames with no rendered content
2. **Content overflow beyond page**: Accept overflow; ODP viewers handle it
3. **Missing images**: Fall back to alt text as text frame
4. **Nested grids**: Recursion through `_render_elem` handles any depth
5. **Code blocks**: Monospace, no highlighting (unlike HTML's pygments)
6. **Strikethrough**: Rendered as plain text (ODF text:span doesn't support strikethrough as a style property easily)
7. **Nested bold+italic**: `_walk_text_children` handles nesting depth-1. Deeper nesting (bold+italic+mono) is rare and collapses to the outermost style

## Not in scope (follow-up)

- Page transitions / animations
- Presenter notes in ODP
- Custom page sizes via frontmatter
- Embedding external images by URL (requires download + add_file)
- Proportional logo sizing from PIL (currently fixed 3cm × 1.3cm)
- Full table cell borders and header background color (currently bold text only)
