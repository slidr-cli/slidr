"""Tests for the HTML renderer's element rendering."""

from slidr.render.html import _render_elem
from slidr.render.ir import Elem


def test_slide_notes_are_js_and_attribute_safe():
    """Multi-line speaker notes must not break the JS array or the data-notes attr.

    Notes flow into two contexts: a JavaScript string array in slidr.js and an
    HTML attribute in shell.html. A raw newline breaks the JS string literal
    (which blanks the whole deck), and an unescaped quote truncates the
    attribute. The JS context must be JSON-encoded; the attribute HTML-escaped.
    """
    from slidr.parser.markdown import parse
    from slidr.render.html import render

    md = '# Title\n\n<!--\nline one\nsay "hi" now\n-->\n'
    doc = parse(md)
    html = render(doc, "", "", (1280, 720))

    # JS array: the note is JSON-encoded, so its newline is escaped, not raw.
    start = html.index("var slideNotes = [")
    array = html[start:html.index("];", start)]
    assert "\\n" in array            # newline escaped for the JS string
    assert "line one" in array
    assert "line one\nsay" not in array   # no raw newline inside the literal

    # HTML attribute: the embedded double-quote is escaped.
    assert 'data-notes="' in html
    assert "&#34;hi&#34;" in html or "&quot;hi&quot;" in html


def test_speaker_linkedin_uses_brand_svg_not_placeholder():
    """linkedin= renders the inlined brand mark, never a Lucide placeholder.

    Lucide dropped all brand icons upstream, so a mapped `linkedin` Lucide
    icon resolves to a "not found" placeholder box. The speaker renderer must
    use the inlined Simple Icons mark instead.
    """
    elem = Elem(kind="speaker", attrs={"name": "The Anh",
                                       "linkedin": "linkedin.com/in/ntheanh201"})
    html = _render_elem(elem)

    # LinkedIn line-icon path signature is present.
    assert "M16 8a6 6 0 0 1 6 6" in html
    # The Lucide "not found" placeholder must never leak through.
    assert "lucide-placeholder" not in html
    assert "data-missing-icon" not in html
    # Link targets the profile.
    assert 'href="https://linkedin.com/in/ntheanh201"' in html


def test_speaker_github_still_uses_lucide_icon():
    """Non-brand contact links keep using their Lucide proxy icon."""
    elem = Elem(kind="speaker", attrs={"name": "The Anh",
                                       "github": "github.com/ntheanh201"})
    html = _render_elem(elem)

    assert "lucide" in html  # git-fork proxy still rendered
    assert "lucide-placeholder" not in html
    assert 'href="https://github.com/ntheanh201"' in html
