"""Tests for the HTML renderer's element rendering."""

from slidr.render.html import _render_elem, base_css
from slidr.render.ir import Elem


def test_print_css_flexes_grids_with_a_grid_heading():
    """Print stylesheet falls back to flexbox for grids with a grid-heading.

    WeasyPrint mis-sizes `1fr` grid tracks when a full-width spanning
    grid-heading (`grid-column: 1 / -1`) is present, collapsing the sibling
    cards to near-zero width. The print CSS must convert those grids to
    flexbox; grids without a grid-heading must stay on the grid path.
    """
    css = base_css()
    assert ".grid:has(> .grid-heading)" in css
    assert ".grid:has(> .grid-heading) > .grid-heading" in css
    # The grid-heading spans a full row in the flex fallback.
    assert "flex: 0 0 100%" in css


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
