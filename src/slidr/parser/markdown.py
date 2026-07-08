"""Markdown parser using markdown-it-py with plugin extensions."""

import re
import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from slidr.parser.ast import (
    Document, Meta, Slide, LayoutType,
    Heading, Paragraph, Grid, Table, Quote, ListNode, AttrNode,
    Text, CodeSpan, SoftBreak,
)
from slidr.plugins.fenced import extract_fenced, interleave_fences
from slidr.plugins.directives import preprocess_directives, extract_attrs, parse_attr_token
from slidr.plugins.cards import group_cards


def parse(input_text: str) -> Document:
    post = frontmatter.loads(input_text)
    raw_meta = dict(post.metadata)
    style_raw = raw_meta.pop("style", "") or ""
    logo_raw = raw_meta.pop("logo", "") or ""

    meta = Meta(
        theme=raw_meta.pop("theme", ""),
        title=raw_meta.pop("title", ""),
        footer=raw_meta.pop("footer", ""),
        paginate=raw_meta.pop("paginate", False),
        size=raw_meta.pop("size", "16:9"),
        style=style_raw,
        logo=logo_raw,
    )

    body = post.content
    slides = []
    for part in body.split("\n---\n"):
        part = part.strip()
        if not part:
            continue
        slides.append(_parse_slide(part))

    return Document(meta=meta, slides=slides)


def _parse_slide(content: str) -> Slide:
    notes = ""
    trimmed = content.strip()
    if trimmed.startswith("<!--"):
        end = trimmed.find("-->")
        if end > 0:
            notes = trimmed[4:end].strip()
            content = trimmed[end + 3:].strip()

    content = re.sub(r"<!--(?!attr:).*?-->", "", content, flags=re.DOTALL).strip()
    content = preprocess_directives(content)

    # Extract fenced blocks
    content, fence_nodes = extract_fenced(content)

    md = MarkdownIt("gfm-like", {"breaks": True, "html": True})
    tokens = md.parse(content)
    nodes = _tokens_to_nodes(tokens)

    nodes = interleave_fences(nodes, fence_nodes)
    nodes = extract_attrs(nodes)
    nodes = group_cards(nodes)

    layout = _detect_layout(nodes)
    return Slide(layout=layout, children=nodes, notes=notes)


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
                    text = ""
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        if tokens[i].type == "inline":
                            text += tokens[i].content
                        i += 1
                    items.append(text.strip())
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
        else:
            i += 1
    return nodes


def _token_inline(token: Token) -> list:
    if token.type == "inline":
        result = []
        for child in (token.children or []):
            result.extend(_token_inline(child))
        return result
    elif token.type == "text":
        return [Text(content=token.content)]
    elif token.type == "code_inline":
        return [CodeSpan(content=token.content)]
    elif token.type == "softbreak":
        return [SoftBreak()]
    elif token.type == "hardbreak":
        return [SoftBreak()]
    return []


def _detect_layout(nodes: list) -> LayoutType:
    has_h1 = any(isinstance(n, Heading) and n.level == 1 for n in nodes)
    has_kicker = any(isinstance(n, AttrNode) and n.type == "kicker" for n in nodes)
    has_speaker = any(isinstance(n, AttrNode) and n.type == "speaker" for n in nodes)
    if has_h1 or has_kicker or has_speaker:
        return LayoutType.TITLE
    for n in nodes:
        if isinstance(n, Grid):
            return {2: LayoutType.GRID2, 3: LayoutType.GRID3, 4: LayoutType.GRID4}.get(n.cols, LayoutType.CONTENT)
    return LayoutType.CONTENT
