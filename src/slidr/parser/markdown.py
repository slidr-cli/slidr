"""Markdown parser using markdown-it-py with fenced block extraction."""

import re
import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from slidr.parser.ast import (
    Document, Meta, Slide, LayoutType,
    Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text, CodeSpan, SoftBreak,
)

FENCE_MARKER = "\u25caFENCE"


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
    content = _preprocess_directives(content)

    # Extract ::: fenced blocks, replace with numbered markers
    content, fence_nodes = _extract_fenced_blocks(content)

    md = MarkdownIt("gfm-like", {"breaks": True, "html": True})
    tokens = md.parse(content)
    nodes = _tokens_to_nodes(tokens)

    nodes = _interleave_fences(nodes, fence_nodes)
    nodes = _extract_attrs(nodes)
    nodes = _group_cards(nodes)

    layout = _detect_layout(nodes)
    return Slide(layout=layout, children=nodes, notes=notes)


def _preprocess_directives(content: str) -> str:
    lines = content.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@") and not stripped.startswith("@@") and " " in stripped:
            directive = stripped[1:].split(" ", 1)
            typ, value = directive[0], directive[1] if len(directive) > 1 else ""
            result.append(f"<!--attr:{typ}:{value}-->")
        else:
            result.append(line)
    return "\n".join(result)


def _extract_fenced_blocks(content: str) -> tuple[str, list]:
    """Extract ::: fence blocks, return (content with markers, parsed nodes)."""
    lines = content.split("\n")
    result = []
    nodes = []
    fence_count = 0
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        if t == ":::":
            i += 1
            continue
        if t.startswith(":::") and not t.startswith("::::"):
            rest = t[3:].strip()
            typ = rest.split()[0].split("{")[0]
            # Find matching :::
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
                card = _parse_card_body(inner_text)
                nodes.append(card)
            elif typ == "grid":
                _, children = _extract_fenced_blocks(inner_text)
                raw = " ".join(rest.split()[1:]).strip("{}")
                cols = 0  # 0 = auto from children
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
                        # Bare word → CSS class
                        if class_:
                            class_ += " " + attr
                        else:
                            class_ = attr
                if cols == 0:
                    cols = len(children) or 2
                nodes.append(Grid(cols=cols, class_=class_, children=children))

            result.append(f"{FENCE_MARKER}_{fence_count}")
            fence_count += 1
            i = j
            continue
        result.append(lines[i])
        i += 1

    return "\n".join(result), nodes


def _parse_card_body(text: str) -> Card:
    header = ""
    body = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("### "):
            header = line[4:]
        elif line:
            body.append(line)
    return Card(header=header, body=body)


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
            if html.startswith("<!--attr:"):
                m = re.match(r"<!--attr:(\w+):(.*)-->", html)
                if m:
                    typ, value = m.group(1), m.group(2)
                    attrs = {}
                    for ma in re.finditer(r'(\w+)="([^"]*)"', value):
                        attrs[ma.group(1)] = ma.group(2)
                    for ma in re.finditer(r'(\w+)=(\S+)', value):
                        if ma.group(1) not in attrs:
                            attrs[ma.group(1)] = ma.group(2)
                    nodes.append(AttrNode(type=typ, value=value, attrs=attrs))
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


def _interleave_fences(nodes: list, fence_nodes: list) -> list:
    """Replace FENCE_MARKER_N paragraphs with actual fence nodes."""
    result = []
    fi = 0
    for node in nodes:
        if isinstance(node, Paragraph) and node.content:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            if text.startswith(FENCE_MARKER):
                if fi < len(fence_nodes):
                    result.append(fence_nodes[fi])
                    fi += 1
                continue
        result.append(node)
    # Append any remaining
    while fi < len(fence_nodes):
        result.append(fence_nodes[fi])
        fi += 1
    return result


def _extract_attrs(nodes: list) -> list:
    result = []
    for node in nodes:
        if isinstance(node, Paragraph) and len(node.content) == 1:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            m = re.match(r"<!--attr:(\w+):(.*)-->", text)
            if m:
                typ, value = m.group(1), m.group(2)
                attrs = {}
                for ma in re.finditer(r'(\w+)="([^"]*)"', value):
                    attrs[ma.group(1)] = ma.group(2)
                for ma in re.finditer(r'(\w+)=(\S+)', value):
                    if ma.group(1) not in attrs:
                        attrs[ma.group(1)] = ma.group(2)
                result.append(AttrNode(type=typ, value=value, attrs=attrs))
                continue
        result.append(node)
    return result


def _group_cards(nodes: list) -> list:
    """Auto-group consecutive Card nodes into Grid."""
    result = []
    i = 0
    while i < len(nodes):
        if isinstance(nodes[i], Card):
            cards = [nodes[i]]
            j = i + 1
            while j < len(nodes) and isinstance(nodes[j], Card):
                cards.append(nodes[j])
                j += 1
            if len(cards) >= 2:
                result.append(Grid(cols=len(cards), children=cards))
            else:
                result.append(cards[0])
            i = j
        else:
            result.append(nodes[i])
            i += 1
    return result


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
