"""Tests for ODF renderer."""

import os
import tempfile

from odfdo import Document, Frame, Paragraph, Span

from slidr.render.ir import Elem
from slidr.render.odf.style import (
    StyleKey, TextStyleKey, GraphicStyleRegistry, TextStyleRegistry,
    set_fonts, set_border_radius, set_border_color, set_tag_colors,
    tag_fill, tag_border, create_table_styles,
)
from slidr.render.odf.layout import (
    LayoutContext, child_ctx, estimate_text_height, estimate_elem_height,
)


def make_elem(kind: str, **kwargs) -> Elem:
    return Elem(kind=kind, **kwargs)


# -- Style registry tests --


def test_graphic_style_registry():
    gr = GraphicStyleRegistry()
    key = StyleKey(font_size=18, color="#333", font_family="Arial")
    name = gr.register(key)
    assert name == "SlidrG_001"
    # Same key returns same name
    assert gr.register(key) == "SlidrG_001"


def test_text_style_registry():
    tr = TextStyleRegistry()
    key = TextStyleKey(weight="bold")
    name = tr.register(key)
    assert name == "SlidrT_001"
    assert tr.register(key) == "SlidrT_001"


def test_tag_colors():
    set_tag_colors({
        "green": ("#e8f5e9", "#0fd05d"),
        "red": ("#ffebee", "#ff7a7a"),
    })
    assert tag_fill("green") == "#e8f5e9"
    assert tag_border("green") == "#0fd05d"
    assert tag_fill("unknown") == "#e3f2fd"  # falls back to default blue


def test_table_styles_created():
    doc = Document("presentation")
    styles = {"card_border_color": "#ddd"}
    _, cell_name = create_table_styles(doc, styles)
    assert cell_name == "SlidrTableCell"
    style = doc.get_style("table-cell", cell_name)
    assert style is not None


# -- Layout tests --


def test_estimate_text_height_empty():
    assert estimate_text_height("", 18, 24.0) == 0.0


def test_estimate_text_height_basic():
    h = estimate_text_height("Hello", 18, 24.0)
    assert h > 0.3  # at least one line


def test_child_ctx():
    ctx = LayoutContext(x=2.0, y=3.0, width=24.0)
    ctx2 = child_ctx(ctx, x=5.0)
    assert ctx2.x == 5.0
    assert ctx2.y == 3.0
    assert ctx2.width == 24.0


def test_estimate_elem_height_card():
    elem = make_elem("card", header="Test", body=["Line 1", "Line 2"], font_size=18)
    h = estimate_elem_height(elem, 24.0)
    assert h > 1.0
