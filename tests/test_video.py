"""Tests for the @video directive: parse, IR, HTML render, ODP skip."""

from slidr.render.html import _render_elem
from slidr.render.ir import build_ir
from slidr.render.odp import _render_elem as _render_elem_odp
from slidr.parser.markdown import parse


def _video_elem():
    doc = parse("@video assets/demo/llm_test.mp4\n")
    elems = build_ir(doc)[0].elements
    return next(e for e in elems if e.kind == "video")


def test_parse_video_directive_becomes_attrnode():
    from slidr.parser.ast import AttrNode
    node = parse("@video assets/demo/llm_test.mp4\n").slides[0].children[0]
    assert isinstance(node, AttrNode)
    assert node.type == "video"
    assert node.value == "assets/demo/llm_test.mp4"


def test_ir_video_elem_has_src():
    elem = _video_elem()
    assert elem.src == "assets/demo/llm_test.mp4"


def test_html_video_renders_video_and_print_fallback():
    html = _render_elem(_video_elem())

    assert 'class="video"' in html
    assert '<video controls preload="metadata" src="assets/demo/llm_test.mp4"' in html
    assert 'poster="assets/demo/llm_test.png"' in html
    assert '<img class="video-print" src="assets/demo/llm_test.png"' in html


def test_odp_skips_video_elem():
    assert _render_elem_odp(_video_elem(), None, None, None, None) == []
