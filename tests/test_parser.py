import pytest
from slidr.parser.markdown import parse
from slidr.parser.ast import Heading, Paragraph, Table, Quote, Card, Grid


def test_parse_simple():
    doc = parse("---\ntheme: test\n---\n\n# Title\n\ntext")
    assert len(doc.slides) == 1
    assert doc.meta.theme == "test"


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
