"""Tests for ODP renderer."""

from slidr.render.ir import Elem
from slidr.render.odp import _merge_text_elements


def make(kind: str, **kwargs) -> Elem:
    return Elem(kind=kind, **kwargs)


def test_merge_text_elements_consecutive():
    result = _merge_text_elements([
        make("heading", text="Title"),
        make("text", text="Body text"),
        make("list", items=["Item 1", "Item 2"]),
    ])
    assert len(result) == 1
    block = result[0]
    assert block.kind == "block"
    assert len(block.children) == 3
    assert block.children[0].kind == "heading"
    assert block.children[1].kind == "text"
    assert block.children[2].kind == "list"


def test_merge_text_elements_separated_by_card():
    result = _merge_text_elements([
        make("text", text="Before"),
        make("card", header="Card"),
        make("text", text="After"),
    ])
    assert len(result) == 3
    assert result[0].kind == "text"  # single text, no wrapper needed
    assert result[1].kind == "card"
    assert result[2].kind == "text"


def test_merge_text_elements_single():
    result = _merge_text_elements([make("text", text="Only text")])
    assert len(result) == 1
    assert result[0].kind == "text"  # single element, no block wrapper


def test_merge_text_elements_empty():
    result = _merge_text_elements([])
    assert result == []


def test_merge_text_elements_all_non_text():
    result = _merge_text_elements([
        make("card", header="A"),
        make("card", header="B"),
    ])
    assert len(result) == 2
    assert result[0].kind == "card"
    assert result[1].kind == "card"


def test_render_list_produces_odf_list():
    """Verify _render_list outputs an ODF <text:list> element."""
    from slidr.render.odp import _render_list, GraphicStyleRegistry, TextStyleRegistry
    from slidr.render.odp import LayoutContext
    from odfdo import Document

    gr = GraphicStyleRegistry()
    tr = TextStyleRegistry()
    odp = Document("presentation")
    ctx = LayoutContext(x=2, y=2, width=24, gap=0.5)

    elem = Elem(
        kind="list", items=["First", "Second", "Third"],
        item_inlines=[], font_size=16, color="#333",
    )
    frames = _render_list(elem, ctx, gr, tr, odp)

    assert len(frames) == 1
    frame = frames[0]
    assert frame.tag == "draw:frame"

    text_box = frame.get_element("draw:text-box")
    assert text_box is not None

    odf_list = text_box.get_element("text:list")
    assert odf_list is not None, "Expected <text:list> in output"

    items = odf_list.get_elements("text:list-item")
    assert len(items) == 3


def test_css_values_propagate_to_odp_styles():
    """Verify font and border-radius from CSS reach the ODP style registry."""
    from slidr.render.odp import (
        GraphicStyleRegistry, StyleKey, set_fonts, set_border_radius,
        _style_key_for,
    )
    from slidr.render.ir import Elem

    set_fonts("My Custom Sans", "My Custom Mono")
    set_border_radius("0.2em")

    gr = GraphicStyleRegistry()
    key = _style_key_for(Elem(kind="text", font_size=18, color="#333"))
    assert key.font_family == "My Custom Sans"

    key2 = _style_key_for(Elem(kind="code", font_size=14, color="#333"))
    assert key2.font_family == "My Custom Mono"

    # Register both body and mono styles
    gr.register(key)
    gr.register(key2)
    from odfdo import Document
    doc = Document("presentation")
    gr.insert_all(doc)

    styles_xml = doc.get_part("styles").serialize().decode()
    assert "My Custom Sans" in styles_xml
    assert "My Custom Mono" in styles_xml

    # Card style should have border-radius
    card_key = StyleKey(font_size=18, color="#333", fill="#e8f5e9",
                        font_family="My Custom Sans", border_radius="0.2em")
    gr2 = GraphicStyleRegistry()
    gr2.register(card_key)
    doc2 = Document("presentation")
    gr2.insert_all(doc2)
    styles2 = doc2.get_part("styles").serialize().decode()
    assert 'corner-radius' in styles2
    assert '0.2em' in styles2
