"""HTML renderer for slidr."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from slidr.parser.ast import (
    Document, Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text, CodeSpan, SoftBreak,
)

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
    dims = doc.meta.dimensions()

    slides = []
    for i, slide in enumerate(doc.slides):
        children = "\n".join(filter(None, (_render_node(n) for n in slide.children)))
        slides.append({
            "num": i + 1, "layout": slide.layout.value, "children": children,
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

    return _env.get_template("shell.html").render(
        title=doc.meta.title or "Presentation", slide_w=dims[0], slide_h=dims[1], css=css, slides=slides,
    )


def render_presenter(doc):
    slides = []
    for slide in doc.slides:
        children = "\n".join(filter(None, (_render_node(n) for n in slide.children)))
        slides.append({"layout": slide.layout.value, "children": children, "notes": slide.notes or ""})
    dims = doc.meta.dimensions()
    css = base_css().replace("SLIDE_W", str(dims[0])).replace("SLIDE_H", str(dims[1]))
    css = css.replace("THEME_CSS", default_theme() + "\n" + (doc.meta.style or "")).replace("LOGO_CSS", "")
    return _env.get_template("presenter.html").render(
        title=doc.meta.title or "Presentation", css=css, slides=slides,
        slide_w=dims[0], slide_h=dims[1])


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
            s += f"<li>{_escape(item)}</li>\n"
        s += "</ul>"
        return s
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
        elif isinstance(n, CodeSpan):
            s += f"<code>{_escape(n.content)}</code>"
        elif isinstance(n, SoftBreak):
            s += " "
    return s


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
