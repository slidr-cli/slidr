"""HTML renderer for slidr."""

from pathlib import Path

from slidr.parser.ast import (
    Document, Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text, CodeSpan, SoftBreak,
)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def render(doc: Document, theme_css: str, logo: str = "") -> str:
    """Render a Document to complete HTML."""
    dims = doc.meta.dimensions()
    ratio = dims[0] / dims[1]

    slides_html = []
    for i, slide in enumerate(doc.slides):
        num = i + 1
        layout = slide.layout.value
        children = "\n".join(_render_node(n) for n in slide.children if _render_node(n))
        footer = doc.meta.footer
        footer_html = ""
        if footer:
            pn = f" &mdash; {num}" if doc.meta.paginate else ""
            footer_html = f"<footer>{footer}{pn}</footer>"

        notes_attr = f' data-notes="{slide.notes}"' if slide.notes else ""
        slides_html.append(
            f'<section class="slide layout-{layout}"{notes_attr}>\n{children}\n{footer_html}\n</section>'
        )

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

    shell = (TEMPLATE_DIR / "shell.html").read_text()
    return shell.format(
        title=doc.meta.title or "Presentation",
        ratio=ratio,
        slide_w=dims[0],
        slide_h=dims[1],
        theme_css=theme_css,
        logo_css=logo_css,
        slides="\n".join(slides_html),
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
            s += f"<li>{_escape(item)}</li>\n"
        s += "</ul>"
        return s
    elif isinstance(node, AttrNode):
        if node.type == "kicker":
            return f'<div class="kicker">{_escape(node.value)}</div>'
        elif node.type == "subtitle":
            return f'<p class="subtitle">{_escape(node.value)}</p>'
        elif node.type == "speaker":
            name = node.attrs.get("name", node.value)
            role = node.attrs.get("role", "")
            return f'<div class="speaker">{_escape(name)}<span>{_escape(role)}</span></div>'
        elif node.type == "tiny":
            return f'<p class="tiny">{_escape(node.value)}</p>'
        elif node.type == "muted":
            return f'<p class="muted">{_escape(node.value)}</p>'
        else:
            return f'<div class="{node.type}">{_escape(node.value)}</div>'
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
