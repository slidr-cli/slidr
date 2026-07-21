"""Markdown parser using markdown-it-py with plugin extensions."""

import re
import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from slidr.parser.ast import (
    Document, Meta, Slide,
    Heading, Paragraph, CodeBlock, Card, Grid, Table, Quote, ListNode, AttrNode,
    Text, Strong, Emphasis, Strikethrough, CodeSpan, Image, SoftBreak, LucideIcon,
)
from slidr.plugins.fenced import extract_fenced, interleave_fences
from slidr.plugins.directives import preprocess_directives, extract_attrs, parse_attr_token
from slidr.plugins.lucide import lucide_plugin
from slidr.plugins.cards import group_cards


def parse(input_text: str) -> Document:
    post = frontmatter.loads(input_text)
    raw_meta = dict(post.metadata)
    style_raw = raw_meta.pop("style", "") or ""
    logo_raw = raw_meta.pop("logo", "") or ""
    logo_dark_raw = raw_meta.pop("logo_dark", "") or ""
    watermark_raw = raw_meta.pop("watermark", "") or ""

    meta = Meta(
        theme=raw_meta.pop("theme", ""),
        title=raw_meta.pop("title", ""),
        footer=raw_meta.pop("footer", ""),
        paginate=raw_meta.pop("paginate", False),
        size=raw_meta.pop("size", "16:9"),
        style=style_raw,
        logo=logo_raw,
        logo_dark=logo_dark_raw,
        watermark=watermark_raw,
        pygments_style=raw_meta.pop("pygments_style", "default"),
        seaborn_theme=raw_meta.pop("seaborn_theme", None) or Meta.seaborn_theme,
        theme_variant=raw_meta.pop("variant", Meta.theme_variant),
    )

    body = post.content
    slides = []
    for part in body.split("\n---\n"):
        part = part.strip()
        if not part:
            continue
        slide = _parse_slide(part)
        if slide is not None:
            slides.append(slide)

    return Document(meta=meta, slides=slides)


def _parse_slide(content: str) -> Slide:
    notes = ""
    # Collect all HTML comments as speaker notes
    note_parts = re.findall(r"<!--(?!attr:)\s*(.*?)\s*-->", content, flags=re.DOTALL)
    if note_parts:
        notes = "\n\n".join(p.strip() for p in note_parts if p.strip())
    # Strip comments from content
    content = re.sub(r"<!--(?!attr:).*?-->", "", content, flags=re.DOTALL).strip()
    content = preprocess_directives(content)

    # Extract fenced blocks
    content, fence_nodes = extract_fenced(content)

    md = MarkdownIt("gfm-like", {"breaks": True, "html": True})
    md.use(lucide_plugin)
    tokens = md.parse(content)
    nodes = _tokens_to_nodes(tokens)

    nodes = interleave_fences(nodes, fence_nodes)
    nodes = extract_attrs(nodes)
    nodes = group_cards(nodes)

    layout = _detect_layout(nodes)
    variant = ""
    hidden = False
    for n in list(nodes):
        if isinstance(n, AttrNode) and n.type == "layout":
            layout = n.value.strip()
            nodes.remove(n)
        elif isinstance(n, AttrNode) and n.type == "variant":
            variant = n.value.strip()
            nodes.remove(n)
        elif isinstance(n, AttrNode) and n.type in ("hidden", "hide"):
            hidden = True
            nodes.remove(n)

    if hidden:
        return None

    return Slide(layout=layout, children=nodes, notes=notes, variant=variant)


def _tokens_to_nodes(tokens: list[Token]) -> list:
    nodes = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open":
            level = int(token.tag[1])
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "heading_close":
                content.extend(_token_inline(tokens[i]))
                i += 1
            nodes.append(Heading(level=level, content=content))
            i += 1
        elif token.type == "paragraph_open":
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                content.extend(_token_inline(tokens[i]))
                i += 1
            if content:
                nodes.append(Paragraph(content=content))
            i += 1
        elif token.type == "blockquote_open":
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "blockquote_close":
                if tokens[i].type == "inline":
                    content.extend(_token_inline(tokens[i]))
                i += 1
            if content:
                nodes.append(Quote(content=content))
            i += 1
        elif token.type == "table_open":
            rows = []
            cur = []
            i += 1
            while i < len(tokens) and tokens[i].type != "table_close":
                t = tokens[i]
                if t.type in ("th_open", "td_open"):
                    i += 1
                    cell = ""
                    while i < len(tokens) and tokens[i].type not in ("th_close", "td_close"):
                        if tokens[i].type == "lucide_icon":
                            cell += _render_lucide_cell(tokens[i])
                        elif tokens[i].type == "inline":
                            for c in tokens[i].children or []:
                                if c.type == "lucide_icon":
                                    cell += _render_lucide_cell(c)
                                else:
                                    cell += c.content or ""
                        else:
                            cell += tokens[i].content
                        i += 1
                    cur.append(cell.strip())
                elif t.type == "tr_close":
                    if cur:
                        rows.append(cur)
                        cur = []
                i += 1
            if cur:
                rows.append(cur)
            if rows:
                nodes.append(Table(headers=rows[0], rows=rows[1:]))
            i += 1
        elif token.type in ("bullet_list_open", "ordered_list_open"):
            close_type = token.type.replace("_open", "_close")
            items = []
            i += 1
            while i < len(tokens) and tokens[i].type != close_type:
                if tokens[i].type == "list_item_open":
                    i += 1
                    inlines = []
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        if tokens[i].type == "inline":
                            inlines.extend(_token_inline(tokens[i]))
                        i += 1
                    items.append(inlines)
                    i += 1
                else:
                    i += 1
            if items:
                nodes.append(ListNode(items=items))
            i += 1
        elif token.type == "inline":
            content = _token_inline(token)
            if content:
                nodes.append(Paragraph(content=content))
            i += 1
        elif token.type == "html_block":
            html = token.content.strip()
            node = parse_attr_token(html)
            if node:
                nodes.append(node)
            i += 1
        elif token.type in ("fence", "code_block"):
            lang = token.info.strip() if token.info else ""
            nodes.append(CodeBlock(content=token.content, language=lang))
            i += 1
        else:
            i += 1
    return nodes


def _token_inline(token: Token) -> list:
    if token.type == "inline":
        return _walk_inline_children(token.children or [])
    elif token.type == "text":
        return [Text(content=token.content)]
    elif token.type == "code_inline":
        return [CodeSpan(content=token.content)]
    elif token.type == "softbreak":
        return [SoftBreak()]
    elif token.type == "hardbreak":
        return [SoftBreak()]
    elif token.type == "image":
        attrs = dict(token.attrs or {})
        return [Image(src=attrs.get("src", ""), alt=token.content or "", title=attrs.get("title", ""))]
    elif token.type == "lucide_icon" or token.type == "svg":
        attrs = dict(token.attrs or {})
        name = attrs.pop("name", "")
        return [LucideIcon(name=name, attrs=attrs)]
    return []


def _walk_inline_children(tokens: list) -> list:
    """Walk inline token children, handling strong/em open/close pairs."""
    result = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "strong_open":
            i += 1
            inner = []
            while i < len(tokens) and tokens[i].type != "strong_close":
                inner.extend(_token_inline(tokens[i]))
                i += 1
            result.append(Strong(children=inner))
        elif t.type == "em_open":
            i += 1
            inner = []
            while i < len(tokens) and tokens[i].type != "em_close":
                inner.extend(_token_inline(tokens[i]))
                i += 1
            result.append(Emphasis(children=inner))
        elif t.type == "s_open":
            i += 1
            inner = []
            while i < len(tokens) and tokens[i].type != "s_close":
                inner.extend(_token_inline(tokens[i]))
                i += 1
            result.append(Strikethrough(children=inner))
        else:
            result.extend(_token_inline(t))
        i += 1
    return result


def _render_lucide_cell(token) -> str:
    """Render a lucide_icon token as SVG for table cells. Delegates to plugin."""
    from slidr.plugins.lucide import render_icon
    attrs = dict(token.attrs or {})
    return render_icon(attrs.pop("name", ""), attrs)


def _detect_layout(nodes: list) -> str:
    has_h1 = any(isinstance(n, Heading) and n.level == 1 for n in nodes)
    has_kicker = any(isinstance(n, AttrNode) and n.type == "kicker" for n in nodes)
    has_speaker = any(isinstance(n, AttrNode) and n.type == "speaker" for n in nodes)
    if has_h1 or has_kicker or has_speaker:
        return "title"
    for n in nodes:
        if isinstance(n, Grid):
            if n.children and all(
                isinstance(c, Card) and "metric" in (c.class_ or "") for c in n.children
            ):
                return f"metrics-{n.cols}" if n.cols else "metrics-2"
            return f"grid-{n.cols}" if n.cols else "grid-2"
    return "content"
