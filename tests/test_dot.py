"""Tests for dot/Graphviz renderer."""

from slidr.render.dot import render_dot_svg, _preprocess


def test_dot_renders_svg_with_injected_css():
    """Verify dot code blocks produce SVG with theme CSS injected."""
    dot = """digraph standard_mode {
    rankdir=TB;
    compound=true;
    newrank=true;

    subgraph cluster_main {
        label="Standard Mode";
        style=filled;
        class="tag-default";
        penwidth=2;
        margin=20;
        node [width=2];

        app [label="Application" class="tag-default" shape=box style=filled];
        mem [label="Memory Interception" class="tag-cyan" shape=box style=filled];
        comp [label="Compute Interception" class="tag-cyan" shape=box style=filled];
        gpu [label="Physical GPU" class="tag-green" shape=box style=filled];

        app -> mem -> comp -> gpu;
    }
}"""
    svg = render_dot_svg(dot, font_family="Liberation Mono", font_size=12)
    assert svg is not None
    assert '<svg' in svg
    assert '.node > polygon' in svg
    assert '.node.cyan' in svg
    assert '.node.green' in svg
    assert 'font-family: Liberation Mono' in svg


def test_dot_preprocess_adds_defaults():
    """Verify _preprocess injects font defaults when not set."""
    content = "digraph { a -> b; }"
    result = _preprocess(content, "Liberation Mono", 12)
    assert 'fontname="Liberation Mono"' in result
    assert "fontsize=12" in result

    content2 = "digraph { node [fontname=Arial fontsize=10]; a -> b; }"
    result2 = _preprocess(content2, "Liberation Mono", 12)
    assert "Arial" in result2
    assert "Liberation Mono" not in result2


def test_dot_handles_css_font_family():
    """Verify _preprocess strips CSS font-family lists to a single name."""
    css_fam = '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace'
    result = _preprocess("digraph { a -> b; }", css_fam, 12)
    assert 'fontname="SFMono-Regular"' in result


def test_dot_full_render_produces_svg():
    """Verify render_dot_svg produces valid SVG output."""
    svg = render_dot_svg("digraph { a -> b; }")
    assert svg is not None
    assert '<svg' in svg
    assert '</svg>' in svg


def test_dot_missing_cli_returns_none():
    """Verify render_dot_svg returns None when dot CLI is missing."""
    import subprocess

    orig_call = subprocess.run
    subprocess.run = lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("no dot"))
    try:
        result = render_dot_svg("digraph { a -> b; }")
        assert result is None
    finally:
        subprocess.run = orig_call
