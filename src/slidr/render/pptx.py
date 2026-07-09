"""PPTX renderer consuming SlideIR with resolved styles."""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from slidr.parser.ast import Document
from slidr.render.ir import build_ir, SlideIR, Elem


def render(doc: Document, output_path: Path, base_css: str = "", theme_css: str = "") -> None:
    dims = doc.meta.dimensions()
    sw, sh = dims[0], dims[1]

    ir_slides = build_ir(doc, base_css, theme_css)

    prs = Presentation()
    prs.slide_width = Inches(sw / 96)
    prs.slide_height = Inches(sh / 96)

    if ir_slides:
        first = ir_slides[0]
        if first.elements:
            bg = first.elements[0].bg or "#ffffff"
            _set_bg(prs.slide_masters[0], bg)

    for slide in ir_slides:
        sld = prs.slides.add_slide(prs.slide_layouts[6])
        top = Pt(5)
        for elem in slide.elements:
            top = _render_elem(sld, elem, Pt(64), top, Pt(sw - 128))

    prs.save(str(output_path))


def _render_elem(sld, e: Elem, left, top, width) -> int:
    if e.kind in ("heading", "text", "quote", "code", "kicker", "subtitle", "tiny"):
        return _textbox(sld, e.text or e.content, left, top, width, e)

    elif e.kind == "list":
        h = Pt(14 * len(e.items))
        txBox = sld.shapes.add_textbox(left, top, width, h)
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, item in enumerate(e.items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"  {item}"
            p.font.size = Pt(e.font_size)
            p.font.color.rgb = _to_rgb(e.color)
        return top + h + Pt(4)

    elif e.kind == "table":
        rows = len(e.rows) + 1
        cols = len(e.headers)
        h = Pt(18 * rows)
        shape = sld.shapes.add_table(rows, cols, left, top, width, h)
        table = shape.table
        for j, hdr in enumerate(e.headers):
            cell = table.cell(0, j)
            cell.text = hdr
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(13)
                p.font.bold = True
        for i, row in enumerate(e.rows):
            for j, ct in enumerate(row):
                cell = table.cell(i + 1, j)
                cell.text = ct
                for p in cell.text_frame.paragraphs:
                    p.font.size = Pt(e.font_size)
                    p.font.color.rgb = _to_rgb(e.color)
        return top + h + Pt(8)

    elif e.kind == "grid":
        if e.layout == "layout-cols":
            cols = len(e.children)
            gap = Pt(16)
            cw = (width - gap * (cols - 1)) / cols
            ct = top
            for i, child in enumerate(e.children):
                ct = _render_elem(sld, child, left + i * (cw + gap), top, cw)
            return ct + Pt(8)
        cols = e.cols or len(e.children) or 2
        gap = Pt(8)
        cw = (width - gap * (cols - 1)) / cols
        ct = top
        for i, child in enumerate(e.children):
            ct = _render_elem(sld, child, left + i * (cw + gap), top, cw)
        return ct + Pt(8)

    elif e.kind == "card":
        ct = top
        if e.header:
            ct = _textbox(sld, e.header, left, ct, width,
                         Elem(kind="heading", level=3, font_size=18, color=e.color, text=e.header))
        for line in e.body:
            ct = _textbox(sld, line, left, ct, width,
                         Elem(kind="text", font_size=e.font_size, color=e.color, text=line))
        return ct

    elif e.kind == "speaker":
        return _textbox(sld, e.text or e.content, left, top, width, e)

    return top


def _textbox(sld, text: str, left, top, width, e: Elem) -> int:
    if not text:
        return top

    is_heading = e.kind == "heading"
    is_quote = e.kind == "quote"

    txBox = sld.shapes.add_textbox(left, top, width, Pt(24))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(e.font_size)
    p.font.bold = is_heading or e.kind == "kicker"
    p.font.color.rgb = _to_rgb(e.color)
    p.font.italic = is_quote
    return top + Pt(18 * max(1, len(text) // 60 + 1)) + Pt(4)


def _to_rgb(hex_color: str) -> RGBColor:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


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
