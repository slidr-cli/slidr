import pytest
from slidr.parser.markdown import parse
from slidr.parser.ast import Heading, Paragraph, Table, Quote, Card, Grid
from slidr.render.odp import _svg_dims, _normalize_svg


def test_parse_simple():
    doc = parse("---\ntheme: test\n---\n\n# Title\n\ntext")
    assert len(doc.slides) == 1
    assert doc.meta.theme == "test"


def test_normalize_svg_negative_origin():
    svg = '<svg viewBox="-10 -5 100 50" width="100%"><rect/></svg>'
    result = _normalize_svg(svg)
    assert 'viewBox="0 0 110 55"' in result
    assert '<g transform' not in result  # no translate wrapper


def test_normalize_svg_positive_origin():
    svg = '<svg viewBox="0 0 100 50" width="100%"><rect/></svg>'
    result = _normalize_svg(svg)
    assert result == svg  # unchanged


def test_normalize_svg_no_viewbox():
    svg = '<svg width="100" height="50"><rect/></svg>'
    result = _normalize_svg(svg)
    assert result == svg  # unchanged


def test_svg_dims_standard():
    svg = '<svg viewBox="0 0 500 300">'
    w, h = _svg_dims(svg)
    assert abs(w - 500 * 0.0353) < 0.1
    assert abs(h - 300 * 0.0353) < 0.1


def test_svg_dims_negative_origin():
    svg = '<svg viewBox="-100 -50 469.5 212.3">'
    w, h = _svg_dims(svg)
    assert abs(w - 469.5 * 0.0353) < 0.1
    assert abs(h - 212.3 * 0.0353) < 0.1


def test_svg_dims_no_viewbox():
    svg = '<svg width="100" height="200">'
    w, h = _svg_dims(svg)
    assert w == 16.0
    assert h == 9.0


def test_heading():
    doc = parse("---\ntheme: t\n---\n\n# Title\n\ntext")
    slide = doc.slides[0]
    assert any(isinstance(n, Heading) and n.level == 1 for n in slide.children)


def test_table():
    doc = parse("---\ntheme: t\n---\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    slide = doc.slides[0]
    assert any(isinstance(n, Table) for n in slide.children)


def test_quote():
    doc = parse("---\ntheme: t\n---\n\n> quoted text")
    slide = doc.slides[0]
    assert any(isinstance(n, Quote) for n in slide.children)


def test_slides():
    doc = parse("---\ntheme: t\n---\n\n## slide 1\n\n---\n\n## slide 2")
    assert len(doc.slides) == 2


def test_hidden_slide():
    doc = parse("---\ntheme: t\n---\n\n# First\n\n---\n\n@hidden\n\n# Hidden\n\n---\n\n# Third")
    assert len(doc.slides) == 2
    from slidr.parser.ast import Heading
    headings = []
    for s in doc.slides:
        for n in s.children:
            if isinstance(n, Heading):
                headings.append(n.content[0].content)
    assert headings == ["First", "Third"]


def test_hide_alias():
    doc = parse("---\ntheme: t\n---\n\n# First\n\n---\n\n@hide\n\n# Hidden\n\n---\n\n# Third")
    assert len(doc.slides) == 2
