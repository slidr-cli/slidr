"""Fenced block extraction: ::: card, ::: grid → AST nodes.

Card/grid ``{...}`` attributes: bare words → CSS classes, ``k=v`` → ``k-v`` classes.
Grid: ``cols=N`` and ``class=name`` used literally.
"""

import re
from markdown_it import MarkdownIt
from slidr.parser.ast import Arrow, Card, CodeBlock, Grid, Node, Notes
from slidr.plugins.lucide import lucide_plugin

_CARD_MD = MarkdownIt("gfm-like", {"breaks": False, "html": True})
_CARD_MD.use(lucide_plugin)

_ICON_RE = re.compile(r'\{icon:(\S+)\s*([^}]*)\}')


def _expand_icons(text: str) -> str:
    """Expand {icon:...} markers using the shared lucide plugin renderer."""
    if not text or "{" not in text:
        return text
    from slidr.plugins.lucide import render_icon, _parse_opts
    def _render(m):
        return render_icon(m.group(1), _parse_opts(m.group(2)))
    return _ICON_RE.sub(_render, text)


def extract_fenced(content: str) -> tuple[str, list[Node]]:
    """Extract ::: fence blocks from content, returning cleaned text and nodes."""
    lines = content.split("\n")
    result = []
    nodes = []
    count = 0
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        if t == ":::":
            i += 1
            continue
        if t.startswith(":::") and not t.startswith("::::"):
            rest = t[3:].strip()
            typ = rest.split()[0].split("{")[0]
            depth = 1
            inner = []
            j = i + 1
            while j < len(lines) and depth > 0:
                lt = lines[j].strip()
                if lt.startswith(":::") and not lt.startswith("::::") and lt != ":::":
                    depth += 1
                elif lt == ":::":
                    depth -= 1
                if depth > 0:
                    inner.append(lines[j])
                j += 1
            inner_text = "\n".join(inner)

            if typ == "card":
                nodes.append(_parse_card(inner_text, rest))
            elif typ == "grid":
                nodes.append(_parse_grid(inner_text, rest))
            elif typ == "arrow":
                nodes.append(_parse_arrow(inner_text))
            elif typ == "notes":
                nodes.append(_parse_notes(inner_text, rest))

            result.append(f"\u25caFENCE_{count}")
            count += 1
            i = j
            continue
        result.append(lines[i])
        i += 1

    return "\n".join(result), nodes


def _parse_card(text: str, rest: str = "") -> Card:
    header = ""
    body = []
    children = []

    lines = text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("```"):
            lang = line[3:].strip()
            inner = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                inner.append(lines[i])
                i += 1
            children.append(CodeBlock(content="\n".join(inner), language=lang))
            i += 1  # skip closing ```
        elif line.startswith("### "):
            header = _expand_markdown(line[4:])
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                li = lines[i].strip()[2:]
                items.append(f"<li>{_expand_markdown(li)}</li>")
                i += 1
            body.append(f"<ul>{''.join(items)}</ul>")
            continue
        elif line:
            rendered = _expand_markdown(line)
            if rendered.strip():
                body.append(rendered)
        i += 1

    class_ = ""
    tag = None
    raw = rest.split("{", 1)[1].rstrip("}") if "{" in rest else ""
    for attr in raw.split(","):
        attr = attr.strip()
        if not attr:
            continue
        if "=" in attr:
            k, v = attr.split("=", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k == "tag":
                tag = v
            else:
                class_ = (class_ + f" {k}-{v}").strip()
        else:
            class_ = (class_ + " " + attr).strip() if class_ else attr

    # ponytail: metric cards: first non-empty line is the value, rest is the label
    if "metric" in class_ and not header and body:
        header = body.pop(0)

    return Card(header=header, body=body, children=children, tag=tag, class_=class_)


def _expand_markdown(text: str) -> str:
    """Render inline markdown (bold, italic, code, images, lucide icons, links)."""
    if not text:
        return text
    text = _expand_icons(text)
    return _CARD_MD.renderInline(text)


def _parse_grid(inner_text: str, rest: str) -> Grid:
    _, children = extract_fenced(inner_text)
    raw = " ".join(rest.split()[1:]).strip("{}")
    cols = 0
    class_ = ""
    for attr in raw.split(","):
        attr = attr.strip()
        if not attr:
            continue
        if "=" in attr:
            k, v = attr.split("=", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k == "cols":
                cols = int(v)
            elif k == "class":
                class_ = v
        else:
            class_ = (class_ + " " + attr).strip() if class_ else attr
    if cols == 0:
        cols = len(children) or 2
    return Grid(cols=cols, class_=class_, children=children)


def _parse_arrow(text: str) -> Arrow:
    return Arrow(content=_expand_icons(text.strip()) or "\u2192")


def _parse_notes(text: str, rest: str) -> Notes:
    tag = ""
    raw = rest.split("{", 1)[1].rstrip("}") if "{" in rest else ""
    for attr in raw.split(","):
        attr = attr.strip()
        if "=" in attr:
            k, v = attr.split("=", 1)
            if k.strip() == "tag":
                tag = v.strip().strip('"')
    return Notes(content=_expand_icons(text.strip()), tag=tag or None)


def interleave_fences(nodes: list[Node], fence_nodes: list[Node]) -> list[Node]:
    """Replace FENCE marker paragraphs with actual fence nodes."""
    from slidr.parser.ast import Paragraph, Text
    result = []
    fi = 0
    for node in nodes:
        if isinstance(node, Paragraph) and node.content:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            if text.startswith("\u25caFENCE_"):
                if fi < len(fence_nodes):
                    result.append(fence_nodes[fi])
                    fi += 1
                continue
        result.append(node)
    while fi < len(fence_nodes):
        result.append(fence_nodes[fi])
        fi += 1
    return result
