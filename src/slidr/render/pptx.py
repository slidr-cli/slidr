"""PPTX renderer using python-pptx. Styling from base.css + theme CSS via tinycss2."""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from slidr.parser.ast import (
    Document, Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode,
    Text as ASText, CodeSpan, SoftBreak,
)
from slidr.theme.parser import parse_theme


def render(doc: Document, output_path: Path) -> None:
    dims = doc.meta.dimensions()
    sw, sh = dims[0], dims[1]

    base = (Path(__file__).parent / "templates" / "base.css").read_text()
    s = parse_theme(base, doc.meta.style)

    prs = Presentation()
    prs.slide_width = Inches(sw / 96)
    prs.slide_height = Inches(sh / 96)

    _set_bg(prs.slide_masters[0], s["bg_color"])

    for slide in doc.slides:
        sld = prs.slides.add_slide(prs.slide_layouts[6])
        top = Pt(5)
        for node in slide.children:
            top = _node(sld, node, Pt(64), top, Pt(sw - 128), s)

    prs.save(str(output_path))


def _node(sld, node, left, top, width, s):
    if isinstance(node, Heading):
        return _text(sld, node.content, left, top, width, s, node.level)
    elif isinstance(node, Paragraph):
        return _text(sld, node.content, left, top, width, s, 0)
    elif isinstance(node, Quote):
        return _text(sld, node.content, left, top, width, s, -1)
    elif isinstance(node, Table):
        return _table(sld, node, left, top, width, s)
    elif isinstance(node, Grid):
        return _grid(sld, node, left, top, width, s)
    elif isinstance(node, ListNode):
        return _list(sld, node, left, top, width, s)
    elif isinstance(node, AttrNode):
        return _attr(sld, node, left, top, width, s)
    return top


def _text(sld, inlines, left, top, width, s, level):
    keys = {-1: "font_quote", 1: "font_h1", 2: "font_h2", 3: "font_h3"}
    size = Pt(s[keys.get(level, "font_body")])
    bold = level > 0

    txBox = sld.shapes.add_textbox(left, top, width, Pt(24))
    tf = txBox.text_frame
    tf.word_wrap = True
    text = _inline(inlines)
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = size
    p.font.bold = bold
    p.font.color.rgb = RGBColor(*s["ink_rgb"])
    return top + Pt(18 * max(1, len(text) // 60 + 1))


def _table(sld, tbl, left, top, width, s):
    rows = len(tbl.rows) + 1
    cols = len(tbl.headers)
    height = Pt(18 * rows)
    shape = sld.shapes.add_table(rows, cols, left, top, width, height)
    table = shape.table

    for j, h in enumerate(tbl.headers):
        cell = table.cell(0, j)
        cell.text = h
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(s["font_small"])
            p.font.bold = True
            p.font.color.rgb = RGBColor(*s["table_header_fg"])

    for i, row in enumerate(tbl.rows):
        for j, ct in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = ct
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(s["font_body"])
                p.font.color.rgb = RGBColor(*s["table_cell_fg"])

    return top + height + Pt(8)


def _grid(sld, grid, left, top, width, s):
    cols = grid.cols or len(grid.children) or 2
    gap = Pt(8)
    cw = (width - gap * (cols - 1)) / cols
    ct = top
    for i, child in enumerate(grid.children):
        ct = _node(sld, child, left + i * (cw + gap), top, cw, s)
    return ct + Pt(8)


def _list(sld, node, left, top, width, s):
    h = Pt(14 * len(node.items))
    txBox = sld.shapes.add_textbox(left, top, width, h)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(node.items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(s["font_body"])
        p.font.color.rgb = RGBColor(*s["ink_rgb"])
    return top + h + Pt(4)


def _attr(sld, node, left, top, width, s):
    size = Pt(s["font_small"])
    text = node.value
    if node.type == "speaker":
        name = node.attrs.get("name", text)
        role = node.attrs.get("role", "")
        text = f"{name}\n{role}"
        size = Pt(s["font_body"])

    txBox = sld.shapes.add_textbox(left, top, width, Pt(18))
    p = txBox.text_frame.paragraphs[0]
    p.text = text
    p.font.size = size
    color = s["accent_rgb"] if node.type == "kicker" else s["muted_rgb"]
    p.font.color.rgb = RGBColor(*color)
    return top + Pt(18) + Pt(4)


def _inline(nodes: list) -> str:
    s = ""
    for n in nodes:
        if isinstance(n, ASText):
            s += n.content
        elif isinstance(n, CodeSpan):
            s += n.content
        elif isinstance(n, SoftBreak):
            s += " "
    return s


def _set_bg(master, color: str):
    from pptx.oxml.ns import qn
    from lxml import etree
    bg = master.element.find(qn('p:cSld'))
    if bg is None:
        return
    bgPr = bg.find(qn('p:bg'))
    if bgPr is None:
        bgPr = etree.SubElement(bg, qn('p:bg'))
    bgPr.clear()
    solid = etree.SubElement(bgPr, qn('p:bgPr'))
    fill = etree.SubElement(solid, qn('a:solidFill'))
    clr = etree.SubElement(fill, qn('a:srgbClr'))
    clr.set('val', color.lstrip('#'))
