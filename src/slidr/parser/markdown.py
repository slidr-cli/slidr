"""Markdown parser using markdown-it-py with custom ::: container support."""

import re
import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.rules_block import StateBlock

from slidr.parser.ast import (
    Document, Meta, Slide, LayoutType,
    Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text, CodeSpan, SoftBreak,
)


def parse(input_text: str) -> Document:
    """Parse markdown with YAML frontmatter into a Document AST."""

    # Split frontmatter
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

    # Split into slides at ---
    slides = []
    for part in body.split("\n---\n"):
        part = part.strip()
        if not part:
            continue
        slides.append(_parse_slide(part))

    return Document(meta=meta, slides=slides)


def _parse_slide(content: str) -> Slide:
    """Parse a single slide's content into a list of AST nodes."""

    # Extract speaker notes (HTML comment at start)
    notes = ""
    trimmed = content.strip()
    if trimmed.startswith("<!--"):
        end = trimmed.find("-->")
        if end > 0:
            notes = trimmed[4:end].strip()
            content = trimmed[end + 3:].strip()

    # Pre-process: convert ::: blocks to markdown-it container syntax
    # and @directives to HTML that we can extract
    content = _preprocess_fences(content)
    content = _preprocess_directives(content)

    # Parse with markdown-it (GFM preset: tables, strikethrough, task lists, autolinks)
    md = MarkdownIt("gfm-like", {"breaks": True, "html": True})

    tokens = md.parse(content)

    # Convert tokens to AST nodes
    nodes = _tokens_to_nodes(tokens)

    # Post-process: convert <fence-card> and <fence-grid> HTML tokens to Card/Grid nodes
    nodes = _extract_fences(nodes)

    # Post-process: convert <attr-*> HTML tokens to AttrNode
    nodes = _extract_attrs(nodes)

    # Detect layout
    layout = _detect_layout(nodes)

    return Slide(layout=layout, children=nodes, notes=notes)


def _preprocess_fences(content: str) -> str:
    """Convert ::: fence blocks to HTML tags that markdown-it preserves."""
    lines = content.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == ":::":
            result.append("</fence-wrapper>")
            i += 1
            continue
        if line.startswith(":::") and not line.startswith("::::"):
            rest = line[3:].strip()
            typ = rest.split()[0].rstrip("{")
            result.append(f"<fence-wrapper><fence-{typ}>")
            i += 1
            continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


def _preprocess_directives(content: str) -> str:
    """Convert @directive lines to HTML tags."""
    lines = content.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@") and not stripped.startswith("@@") and " " in stripped:
            directive = stripped[1:].split(" ", 1)
            typ = directive[0]
            value = directive[1] if len(directive) > 1 else ""
            result.append(f"<attr-{typ}>{value}</attr-{typ}>")
        else:
            result.append(line)
    return "\n".join(result)


def _tokens_to_nodes(tokens: list[Token]) -> list:
    """Convert markdown-it tokens to AST nodes."""
    nodes = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1])
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "heading_close":
                inodes = _token_to_inline(tokens[i])
                content.extend(inodes)
                i += 1
            nodes.append(Heading(level=level, content=content))
            i += 1  # skip heading_close

        elif token.type == "paragraph_open":
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                inodes = _token_to_inline(tokens[i])
                content.extend(inodes)
                i += 1
            if content:
                nodes.append(Paragraph(content=content))
            i += 1  # skip paragraph_close

        elif token.type == "blockquote_open":
            i += 1
            content = []
            while i < len(tokens) and tokens[i].type != "blockquote_close":
                if tokens[i].type == "inline":
                    inodes = _token_to_inline(tokens[i])
                    content.extend(inodes)
                i += 1
            if content:
                nodes.append(Quote(content=content))
            i += 1

        elif token.type == "table_open":
            headers, rows = [], []
            i += 1
            while i < len(tokens) and tokens[i].type != "table_close":
                if tokens[i].type == "thead_open":
                    i += 1
                    while i < len(tokens) and tokens[i].type != "thead_close":
                        if tokens[i].type == "tr_open":
                            i += 1
                            while i < len(tokens) and tokens[i].type != "tr_close":
                                if tokens[i].type in ("th_open", "td_open"):
                                    i += 1
                                    cell = ""
                                    while i < len(tokens) and tokens[i].type not in ("th_close", "td_close"):
                                        cell += tokens[i].content
                                        i += 1
                                    headers.append(cell.strip())
                                i += 1
                            i += 1  # skip tr_close
                        i += 1

                elif tokens[i].type == "tbody_open":
                    i += 1
                    while i < len(tokens) and tokens[i].type != "tbody_close":
                        if tokens[i].type == "tr_open":
                            i += 1
                            row = []
                            while i < len(tokens) and tokens[i].type != "tr_close":
                                if tokens[i].type in ("th_open", "td_open"):
                                    i += 1
                                    cell = ""
                                    while i < len(tokens) and tokens[i].type not in ("th_close", "td_close"):
                                        cell += tokens[i].content
                                        i += 1
                                    row.append(cell.strip())
                                i += 1
                            if row:
                                rows.append(row)
                            i += 1  # skip tr_close
                        i += 1
                i += 1
            if headers or rows:
                nodes.append(Table(headers=headers, rows=rows))
            i += 1

        elif token.type == "bullet_list_open" or token.type == "ordered_list_open":
            items = []
            i += 1
            while i < len(tokens) and tokens[i].type not in ("bullet_list_close", "ordered_list_close"):
                if tokens[i].type == "list_item_open":
                    i += 1
                    item_text = ""
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        if tokens[i].type == "inline":
                            item_text += tokens[i].content
                        i += 1
                    items.append(item_text.strip())
                    i += 1
                else:
                    i += 1
            if items:
                nodes.append(ListNode(items=items))
            i += 1

        elif token.type == "html_block":
            html = token.content.strip()
            nodes.append(_html_to_node(html))
            i += 1

        elif token.type == "inline":
            # Standalone inline (e.g., image or raw text not in paragraph)
            content = _token_to_inline(token)
            if content:
                nodes.append(Paragraph(content=content))
            i += 1

        else:
            i += 1

    return nodes


def _token_to_inline(token: Token) -> list:
    """Convert a single markdown-it token to inline AST nodes."""
    if token.type == "inline":
        result = []
        for child in (token.children or []):
            result.extend(_token_to_inline(child))
        return result
    elif token.type == "text":
        return [Text(content=token.content)]
    elif token.type == "strong_open":
        return []  # handled by parser chasing content
    elif token.type == "code_inline":
        return [CodeSpan(content=token.content)]
    elif token.type == "softbreak":
        return [SoftBreak()]
    elif token.type == "hardbreak":
        return [SoftBreak()]
    return []


def _html_to_node(html: str):
    """Convert HTML block (from pre-processing) back to AST node."""
    html = html.strip()

    if html.startswith("<attr-"):
        m = re.match(r"<attr-(\w+)>(.*)</attr-\1>", html)
        if m:
            typ, value = m.group(1), m.group(2)
            return AttrNode(type=typ, value=value)

    if html.startswith("<fence-card"):
        return _parse_fence_card(html)

    if html.startswith("<fence-grid"):
        return _parse_fence_grid(html)

    # Pass through as plain text
    return Paragraph(content=[Text(content=html)])


def _parse_fence_card(html: str) -> "Node":
    """Parse <fence-card> HTML back to Card node."""
    m = re.search(r"<fence-card>(.*)</fence-card>", html, re.DOTALL)
    if not m:
        return Paragraph(content=[Text(content=html)])

    inner = m.group(1).strip()
    lines = inner.split("\n")
    header = ""
    body = []

    for line in lines:
        line = line.strip()
        if line.startswith("### "):
            header = line[4:]
        elif line:
            body.append(line)

    return Card(header=header, body=body)


def _parse_fence_grid(html: str) -> "Node":
    """Parse <fence-grid> HTML back to Grid node with nested children."""
    # Grid contains nested fence-card children
    m = re.search(r"<fence-grid>(.*)</fence-grid>", html, re.DOTALL)
    if not m:
        return Paragraph(content=[Text(content=html)])

    inner = m.group(1)
    children = []

    # Find all fence-card blocks
    for card_m in re.finditer(r"<fence-card>(.*?)</fence-card>", inner, re.DOTALL):
        children.append(_parse_fence_card(card_m.group(0)))

    return Grid(cols=len(children) or 2, children=children)


def _extract_fences(nodes: list) -> list:
    """Post-process: convert fence placeholder paragraphs to actual nodes."""
    result = []
    pending = []
    in_grid = False

    for node in nodes:
        if isinstance(node, Paragraph) and len(node.content) == 1:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            if text.startswith("<fence-grid>"):
                in_grid = True
                pending = [text]
                continue
            elif text.startswith("<fence-card>"):
                if in_grid:
                    pending.append(text)
                else:
                    result.append(_parse_fence_card(text))
                continue
            elif text == "</fence-wrapper>":
                if in_grid and pending:
                    inner = "\n".join(pending)
                    children = []
                    for card_m in re.finditer(r"<fence-card>(.*?)</fence-card>", inner, re.DOTALL):
                        children.append(_parse_fence_card(card_m.group(0)))
                    result.append(Grid(cols=len(children) or 2, children=children))
                in_grid = False
                pending = []
                continue

        if not in_grid:
            result.append(node)

    return result


def _extract_attrs(nodes: list) -> list:
    """Post-process: convert <attr-*> paragraphs to AttrNodes."""
    result = []
    for node in nodes:
        if isinstance(node, Paragraph) and len(node.content) == 1:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            m = re.match(r"<attr-(\w+)>(.*)</attr-\1>", text)
            if m:
                result.append(AttrNode(type=m.group(1), value=m.group(2)))
                continue
        result.append(node)
    return result


def _detect_layout(nodes: list) -> LayoutType:
    """Auto-detect slide layout from child nodes."""
    has_h1 = any(isinstance(n, Heading) and n.level == 1 for n in nodes)
    has_kicker = any(isinstance(n, AttrNode) and n.type == "kicker" for n in nodes)
    has_speaker = any(isinstance(n, AttrNode) and n.type == "speaker" for n in nodes)

    if has_h1 or has_kicker or has_speaker:
        return LayoutType.TITLE

    for n in nodes:
        if isinstance(n, Grid):
            return {2: LayoutType.GRID2, 3: LayoutType.GRID3, 4: LayoutType.GRID4}.get(n.cols, LayoutType.CONTENT)

    return LayoutType.CONTENT
