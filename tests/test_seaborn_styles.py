"""Tests for seaborn style loading -- CSS theme parsing and palette fallback."""

import pytest
from slidr.render.seaborn import _css_theme_rcparams, set_theme


class TestCssThemeRcparams:
    """Verify CSS themes are parsed into correct matplotlib rcParams."""

    def test_kcd_vietnam_facecolor(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style is not None
        assert style["axes.facecolor"] == "#F6ECD9"

    def test_kcd_vietnam_edgecolor(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["axes.edgecolor"] == "#7A0504"

    def test_kcd_vietnam_text_color(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["text.color"] == "#3a2020"

    def test_kcd_vietnam_patch_edge(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["patch.edgecolor"] == "#F1C560"

    def test_kcd_vietnam_tick_colors(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["xtick.color"] == "#7a6a5a"

    def test_kcd_vietnam_font(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert "Roboto" in style["font.sans-serif"]

    def test_kubecon_japan_facecolor(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style is not None
        assert style["axes.facecolor"] == "#f5f6fa"

    def test_kubecon_japan_edgecolor(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["axes.edgecolor"] == "#3939D8"

    def test_kubecon_japan_text_color(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["text.color"] == "#2a2a5a"

    def test_kubecon_japan_patch_edge(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["patch.edgecolor"] == "#DB1E3D"

    def test_kubecon_japan_tick_colors(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["xtick.color"] == "#6a7a99"

    def test_missing_theme_returns_none(self):
        assert _css_theme_rcparams("nonexistent") is None

    def test_default_theme_returns_style(self):
        style = _css_theme_rcparams("default")
        assert style is not None
        assert isinstance(style, dict)


class TestSetTheme:
    """Verify set_theme applies CSS styles and falls back to seaborn palettes."""

    def test_kcd_vietnam_applies_style(self):
        set_theme("kcd_vietnam")
        from slidr.render import seaborn
        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_kubecon_japan_applies_style(self):
        set_theme("kubecon_japan")
        from slidr.render import seaborn
        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_default_theme_applies_style(self):
        set_theme("default")
        from slidr.render import seaborn
        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_muted_is_palette_fallback(self):
        set_theme("muted")
        from slidr.render import seaborn
        assert seaborn._palette == "muted"
        assert seaborn._style is None

    def test_deep_is_palette_fallback(self):
        set_theme("deep")
        from slidr.render import seaborn
        assert seaborn._palette == "deep"

    def test_unknown_falls_back_to_palette(self):
        set_theme("nonexistent_style_xyz")
        from slidr.render import seaborn
        assert seaborn._palette == "nonexistent_style_xyz"

    def test_empty_string_defaults_to_paired(self):
        set_theme("")
        from slidr.render import seaborn
        assert seaborn._palette == "Paired"

    def test_backward_compat_alias(self):
        from slidr.render.seaborn import set_palette, set_theme
        assert set_palette is set_theme
