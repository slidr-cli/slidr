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

from slidr.parser.ast import (
    Document, Heading, Paragraph, CodeBlock, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text, Strong, Emphasis, Strikethrough, CodeSpan, Image, SoftBreak,
)
from slidr.plugins.layouts import apply_layout, KNOWN_LAYOUTS

_pygments_style = "default"

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
    global _pygments_style
    dims = doc.meta.dimensions()

    slides = []
    for i, slide in enumerate(doc.slides):
        layout = slide.layout
        nodes = slide.children

        heading_html = ""
        body_nodes = nodes
        if nodes and isinstance(nodes[0], Heading) and nodes[0].level <= 2:
            heading_html = _render_node(nodes[0]) or ""
            body_nodes = nodes[1:]

        if layout in KNOWN_LAYOUTS:
            body_html = apply_layout(body_nodes, layout, _render_node)
        else:
            body_html = "\n".join(filter(None, (_render_node(n) for n in body_nodes)))

        if body_html.strip():
            heading_html += '\n<div class="slide-body">\n' + body_html + '\n</div>'
        children = heading_html or body_html
        slides.append({
            "num": i + 1, "layout": layout, "children": children,
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


def _render_node(node) -> str | None:
    if isinstance(node, Heading):
        tag = f"h{node.level}"
        content = _render_inline(node.content)
        return f"<{tag}>{content}</{tag}>"
    elif isinstance(node, Paragraph):
        content = _render_inline(node.content)
        return f"<p>{content}</p>" if content else None
    elif isinstance(node, Quote):
        content = _render_inline(node.content)
        return f'<div class="quote">{content}</div>' if content else None
    elif isinstance(node, Table):
        s = "<table>\n<thead>\n<tr>"
        for h in node.headers:
            s += f"<th>{_escape(h)}</th>"
        s += "</tr>\n</thead>\n<tbody>\n"
        for row in node.rows:
            s += "<tr>"
            for cell in row:
                s += f"<td>{_escape(cell)}</td>"
            s += "</tr>\n"
        s += "</tbody>\n</table>"
        return s
    elif isinstance(node, Grid):
        cols = node.cols or len(node.children) or 2
        cls = "grid"
        if node.class_:
            cls += f" {node.class_}"
        style = f"grid-template-columns: repeat({cols}, 1fr); gap: 16px;"
        children = "\n".join(filter(None, (_render_node(c) for c in node.children)))
        return f'<div class="{cls}" style="{style}">\n{children}\n</div>'
    elif isinstance(node, Card):
        cls = "card"
        if node.class_:
            cls += f" {node.class_}"
        s = f'<div class="{cls}">\n'
        if node.header:
            s += f"<h3>{_escape(node.header)}</h3>\n"
        for line in node.body:
            s += f"<p>{_escape(line)}</p>\n"
        s += "</div>"
        return s
    elif isinstance(node, ListNode):
        s = "<ul>\n"
        for item in node.items:
            content = _render_inline(item)
            s += f"<li>{content}</li>\n"
        s += "</ul>"
        return s
    elif isinstance(node, CodeBlock):
        if node.language == "d2":
            return _render_d2(node.content)
        return _highlight_code(node.content, node.language)
    elif isinstance(node, AttrNode):
        if node.type == "speaker":
            name = node.attrs.get("name", node.value)
            role = node.attrs.get("role", "")
            text = f"{_escape(name)} | <span class=\"role\">{_escape(role)}</span>" if role else _escape(name)
            return f'<div class="speaker">{text}</div>'
        tag = "div" if node.type in ("kicker", "speaker") else "p"
        return f'<{tag} class="{node.type}">{_escape(node.value)}</{tag}>'
    return None


def _render_inline(nodes: list) -> str:
    s = ""
    for n in nodes:
        if isinstance(n, Text):
            s += _escape(n.content)
        elif isinstance(n, Strong):
            s += f"<strong>{_render_inline(n.children)}</strong>"
        elif isinstance(n, Emphasis):
            s += f"<em>{_render_inline(n.children)}</em>"
        elif isinstance(n, Strikethrough):
            s += f"<s>{_render_inline(n.children)}</s>"
        elif isinstance(n, CodeSpan):
            s += f"<code>{_escape(n.content)}</code>"
        elif isinstance(n, Image):
            title = f' title="{_escape(n.title)}"' if n.title else ""
            s += f'<img src="{_escape(n.src)}" alt="{_escape(n.alt)}"{title}>'
        elif isinstance(n, SoftBreak):
            s += " "
    return s


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


def _render_d2(content: str) -> str:
    with tempfile.NamedTemporaryFile(suffix='.d2', mode='w', delete=False) as f:
        f.write(content)
        infile = f.name
    outfile = infile + '.svg'
    try:
        result = subprocess.run(
            ['d2', '--theme=0', '--pad=0', infile, outfile],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(outfile):
            with open(outfile) as f:
                svg = f.read()
            return f'<div class="d2">\n{svg}\n</div>'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    finally:
        os.unlink(infile)
        if os.path.exists(outfile):
            os.unlink(outfile)
    return f'<pre class="d2-fallback"><code>{_escape(content)}</code></pre>'


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
