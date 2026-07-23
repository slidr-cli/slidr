"""HTML renderer for slidr."""

import os
import subprocess
import tempfile
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from slidr.parser.ast import Document
from slidr.render.ir import build_ir, SlideIR, Elem
from slidr.plugins.layouts import KNOWN_LAYOUTS

_pygments_style = "default"

from slidr.render.ir import build_ir, SlideIR, Elem

_BRAND_ICON_SVGS = {
    "linkedin": (
        '<svg class="speaker-icon" xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'style="height:1em;width:auto;vertical-align:middle">'
        '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>'
        '<rect width="4" height="12" x="2" y="9"/>'
        '<circle cx="4" cy="4" r="2"/></svg>'
    ),
}

TEMPLATE_DIR = Path(__file__).parent / "templates"
THEME_DIR = Path(__file__).parent.parent / "themes"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)


def default_theme() -> str:
    p = THEME_DIR / "default.css"
    return p.read_text() if p.exists() else ""


def load_theme(name: str) -> str:
    """Load a named theme CSS file. Falls back to default if not found."""
    p = THEME_DIR / f"{name}.css"
    return p.read_text() if p.exists() else default_theme()


def base_css() -> str:
    p = TEMPLATE_DIR / "base.css"
    return p.read_text() if p.exists() else ""


def render(doc: Document, theme_css: str, assembled_css: str, dims: tuple[int, int], logo: str = "") -> str:
    from slidr.render.seaborn import set_palette

    global _pygments_style
    _pygments_style = doc.meta.pygments_style or "default"
    set_palette(doc.meta.seaborn_theme)

    ir_slides = build_ir(doc, base_css(), theme_css)

    slides = []
    for i, slide in enumerate(ir_slides):
        children = _render_slide(slide)
        slides.append({
            "num": i + 1, "layout": slide.layout, "children": children,
            "notes": slide.notes, "footer": doc.meta.footer or "", "paginate": doc.meta.paginate or False,
            "variant": slide.variant or doc.meta.theme_variant,
            "transition": slide.transition or doc.meta.transition or "",
        })

    return _env.get_template("shell.html").render(
        title=doc.meta.title or "Presentation",
        slide_w=dims[0], slide_h=dims[1],
        css=assembled_css, slides=slides,
        variant=doc.meta.theme_variant or "light",
    )


def _render_slide(slide: SlideIR) -> str:
    elems = slide.elements
    heading_html = ""
    if elems and elems[0].kind == "heading":
        heading_html = _render_elem(elems[0])
        elems = elems[1:]
    if elems and elems[0].kind == "subtitle":
        heading_html += "\n" + _render_elem(elems[0])
        elems = elems[1:]

    body_html = "\n".join(filter(None, (_render_elem(e) for e in elems)))
    if body_html.strip():
        heading_html += '\n<div class="slide-body">\n' + body_html + '\n</div>'
    return heading_html or body_html


def _render_elem(e: Elem) -> str:
    if e.kind == "heading":
        tag = f"h{e.level}"
        return f"<{tag}>{e.content}</{tag}>"
    elif e.kind == "text":
        return f"<p>{e.content}</p>" if e.content else ""
    elif e.kind == "quote":
        return f'<div class="quote">{e.content}</div>' if e.content else ""
    elif e.kind == "code":
        if e.language == "mermaid":
            return _render_mermaid(e.content, e.svg)
        if e.language == "seaborn":
            return _render_seaborn_html(e.content, e.svg)
        if e.language == "dot":
            return _render_dot_html(e.content, e.svg)
        return _highlight_code(e.content, e.language)
    elif e.kind == "list":
        s = "<ul>\n"
        for item in e.items:
            s += f"<li>{item}</li>\n"
        s += "</ul>"
        return s
    elif e.kind == "table":
        s = "<table>\n<thead>\n<tr>"
        for h in e.headers:
            s += f"<th>{_maybe_escape(h)}</th>"
        s += "</tr>\n</thead>\n<tbody>\n"
        for row in e.rows:
            s += "<tr>"
            for cell in row:
                s += f"<td>{_maybe_escape(cell)}</td>"
            s += "</tr>\n"
        s += "</tbody>\n</table>"
        return s
    elif e.kind == "grid":
        if e.layout:
            cls = f"{e.layout}"
            if "compare" in cls:
                # children: col-left, arrow, col-right
                parts = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
                return f'<div class="{cls}">\n{parts}\n</div>'
            children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
            return f'<div class="{cls}">\n{children}\n</div>'
        cols = e.cols or len(e.children) or 2
        style = f"grid-template-columns: repeat({cols}, 1fr); gap: 16px;"
        cls = "grid"
        if e.class_:
            cls += f" {e.class_}"
        children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
        return f'<div class="{cls}" style="{style}">\n{children}\n</div>'
    elif e.kind == "card":
        cls = "card"
        if e.tag:
            cls += f" tag-{e.tag}"
        if e.class_:
            cls += f" {e.class_}"
        s = f'<div class="{cls}">\n'
        if e.header:
            s += f"<h3>{_maybe_escape(e.header)}</h3>\n"
        for line in e.body:
            line = _maybe_escape(line)
            if line.startswith("<ul") or line.startswith("<ol"):
                s += line + "\n"
            else:
                s += f"<p>{line}</p>\n"
        for child in e.children:
            s += _render_elem(child) + "\n"
        s += "</div>"
        return s
    elif e.kind == "arrow":
        return f'<div class="card-arrow">{e.content}</div>'
    elif e.kind == "row":
        cols = len(e.children)
        children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
        return f'<div class="row" style="display:grid;grid-template-columns:repeat({cols},1fr);gap:1em">\n{children}\n</div>'
    elif e.kind == "notes":
        cls = "notes"
        if e.tag:
            cls += f" tag-{e.tag}"
        return f'<div class="{cls}">{e.content}</div>'
    elif e.kind == "speaker":
        from slidr.plugins.lucide import render_icon
        name = e.attrs.get("name", e.content)
        role = e.attrs.get("role", "")
        text = f"{_escape(name)}<br><span class=\"role\">{_escape(role)}</span>" if role else _escape(name)
        links = []
        contact_icons = {"github": "git-fork", "twitter": "bird", "email": "mail", "website": "globe"}
        for key in ("github", "twitter", "email", "linkedin", "website"):
            val = e.attrs.get(key, "")
            if val:
                icon = contact_icons.get(key, "link")
                href = val if "://" in val else f"https://{val}" if key != "email" else f"mailto:{val}"
                label = val.replace("https://", "").replace("mailto:", "")
                svg = _BRAND_ICON_SVGS.get(key) or render_icon(icon, {"cls": "speaker-icon"})
                links.append(f'<a href="{_escape(href)}" target="_blank">{svg} {_escape(label)}</a>')
        if links:
            text += '<br><span class="speaker-links">' + "".join(links) + "</span>"
        return f'<div class="speaker">{text}</div>'
    elif e.kind in ("kicker", "subtitle", "tiny"):
        return f'<p class="{e.kind}">{e.content}</p>'
    return ""


def _highlight_code(content: str, language: str) -> str:
    try:
        lexer = get_lexer_by_name(language, stripall=True) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=True, style=_pygments_style)
    highlighted = highlight(content, lexer, formatter)
    cls = f' class="highlight language-{language}"' if language else ' class="highlight"'
    return f'<pre{cls}><code>{highlighted}</code></pre>'


def _pygments_css(style: str = "default") -> str:
    formatter = HtmlFormatter(style=style)
    css = formatter.get_style_defs('.slide .highlight')
    return f"\n/* ---- pygments ---- */\n{css}\n"


def _render_seaborn_html(content: str, svg: str = "") -> str:
    if svg:
        return f'<div class="seaborn-plot">\n{svg}\n</div>'
    return f'<pre class="seaborn-fallback"><code>{_escape(content)}</code></pre>'


def _render_mermaid(content: str, svg: str = "") -> str:
    if svg:
        return f'<div class="mermaid">\n{svg}\n</div>'
    return f'<pre class="mermaid-fallback"><code>{_escape(content)}</code></pre>'


def _render_dot_html(content: str, svg: str = "") -> str:
    if svg:
        return f'<div class="graphviz-plot">\n{svg}\n</div>'
    return f'<pre class="dot-fallback"><code>{_escape(content)}</code></pre>'


def _normalize_viewbox(svg: str) -> str:
    import re
    m = re.search(r'viewBox="([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)"', svg)
    if not m:
        return svg
    x, y, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    if x >= 0 and y >= 0:
        return svg
    new_w, new_h = w + abs(x), h + abs(y)
    return svg.replace(m.group(0), f'viewBox="0 0 {new_w:g} {new_h:g}"', 1)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _maybe_escape(s: str) -> str:
    """Escape HTML unless the string already contains HTML tags."""
    return s if "<" in s and ">" in s else _escape(s)
