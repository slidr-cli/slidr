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

TEMPLATE_DIR = Path(__file__).parent / "templates"
THEME_DIR = Path(__file__).parent.parent / "themes"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)


def default_theme() -> str:
    p = THEME_DIR / "default.css"
    return p.read_text() if p.exists() else ""


def base_css() -> str:
    p = TEMPLATE_DIR / "base.css"
    return p.read_text() if p.exists() else ""


def render(doc: Document, theme_css: str, logo: str = "") -> str:
    from slidr.render.seaborn import set_palette

    global _pygments_style
    dims = doc.meta.dimensions()
    _pygments_style = doc.meta.pygments_style or "default"
    set_palette(doc.meta.seaborn_theme)

    ir_slides = build_ir(doc, base_css(), default_theme() + "\n" + theme_css)

    slides = []
    for i, slide in enumerate(ir_slides):
        children = _render_slide(slide)
        slides.append({
            "num": i + 1, "layout": slide.layout, "children": children,
            "notes": slide.notes, "footer": doc.meta.footer or "", "paginate": doc.meta.paginate or False,
        })

    logo_css = ""
    if logo:
        logo_css = f"""section::before {{
  content: "";
  position: absolute;
  top: 4%;
  right: 5%;
  width: 14%;
  height: 0;
  padding-bottom: 6%;
  background: url("{logo}") center / contain no-repeat;
  opacity: 0.92;
}}"""

    css = base_css().replace('SLIDE_W', str(dims[0])).replace('SLIDE_H', str(dims[1]))
    css = css.replace('THEME_CSS', default_theme() + '\n' + theme_css).replace('LOGO_CSS', logo_css)
    css = css.replace("{theme_css}", default_theme() + "\n" + theme_css).replace("{logo_css}", logo_css)
    pstyle = doc.meta.pygments_style or "default"
    _pygments_style = pstyle
    css += _pygments_css(pstyle)

    return _env.get_template("shell.html").render(
        title=doc.meta.title or "Presentation", slide_w=dims[0], slide_h=dims[1], css=css, slides=slides,
    )


def _render_slide(slide: SlideIR) -> str:
    elems = slide.elements
    heading_html = ""
    if elems and elems[0].kind == "heading":
        heading_html = _render_elem(elems[0])
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
            return _render_mermaid(e.content)
        if e.language == "seaborn":
            return _render_seaborn_html(e.content)
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
            s += f"<th>{_escape(h)}</th>"
        s += "</tr>\n</thead>\n<tbody>\n"
        for row in e.rows:
            s += "<tr>"
            for cell in row:
                s += f"<td>{_escape(cell)}</td>"
            s += "</tr>\n"
        s += "</tbody>\n</table>"
        return s
    elif e.kind == "grid":
        if e.layout:
            cls = f"{e.layout}"
            if "card-compare" in cls:
                left = _render_elem(e.children[0]) if len(e.children) > 0 else ""
                right = _render_elem(e.children[1]) if len(e.children) > 1 else ""
                return f'<div class="{cls}">\n{left}\n<div class="card-arrow">\u2192</div>\n{right}\n</div>'
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
            s += f"<h3>{_escape(e.header)}</h3>\n"
        for line in e.body:
            s += f"<p>{_escape(line)}</p>\n"
        s += "</div>"
        return s
    elif e.kind == "speaker":
        name = e.attrs.get("name", e.content)
        role = e.attrs.get("role", "")
        text = f"{_escape(name)} | <span class=\"role\">{_escape(role)}</span>" if role else _escape(name)
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


def _render_seaborn_html(content: str) -> str:
    from slidr.render.seaborn import render_seaborn_svg

    svg = render_seaborn_svg(content)
    if svg:
        return f'<div class="seaborn-plot">\n{svg}\n</div>'
    return f'<pre class="seaborn-fallback"><code>{_escape(content)}</code></pre>'


def _render_mermaid(content: str) -> str:
    try:
        from mmdc import render as render_mmd
        d = render_mmd(content)
        svg = _normalize_viewbox(d.svg())
        return f'<div class="mermaid">\n{svg}\n</div>'
    except Exception:
        return f'<pre class="mermaid-fallback"><code>{_escape(content)}</code></pre>'


def _render_seaborn_html(content: str) -> str:
    from slidr.render.seaborn import render_seaborn_svg

    svg = render_seaborn_svg(content)
    if svg:
        return f'<div class="seaborn-plot">\n{svg}\n</div>'
    return f'<pre class="seaborn-fallback"><code>{_escape(content)}</code></pre>'


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
