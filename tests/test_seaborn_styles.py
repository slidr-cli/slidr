"""Tests for seaborn style loading and slidr seaborn_styles package."""

import importlib
import pytest


class TestKcdVietnamStyle:
    def test_module_exists(self):
        mod = importlib.import_module("slidr.seaborn_styles.kcd_vietnam")
        assert hasattr(mod, "STYLE")

    def test_style_is_dict(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert isinstance(STYLE, dict)

    def test_has_palette(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert "axes.prop_cycle" in STYLE

    def test_facecolor_matches_css(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE["axes.facecolor"] == "#F6ECD9"

    def test_edgecolor_matches_accent(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE["axes.edgecolor"] == "#7A0504"

    def test_foreground_matches_css(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE["text.color"] == "#3a2020"

    def test_patch_edge_is_gold(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE["patch.edgecolor"] == "#F1C560"

    def test_tick_colors_match_dimmed(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE["xtick.color"] == "#7a6a5a"

    def test_based_on_pastel(self):
        from slidr.seaborn_styles.kcd_vietnam import STYLE
        assert STYLE.get("seaborn_palette") == "pastel"


class TestKubeconJapanStyle:
    def test_module_exists(self):
        mod = importlib.import_module("slidr.seaborn_styles.kubecon_japan")
        assert hasattr(mod, "STYLE")

    def test_facecolor_matches_css(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE["axes.facecolor"] == "#f5f6fa"

    def test_edgecolor_matches_accent(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE["axes.edgecolor"] == "#3939D8"

    def test_foreground_matches_css(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE["text.color"] == "#2a2a5a"

    def test_patch_edge_is_secondary(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE["patch.edgecolor"] == "#DB1E3D"

    def test_tick_colors_match_dimmed(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE["xtick.color"] == "#6a7a99"

    def test_based_on_pastel(self):
        from slidr.seaborn_styles.kubecon_japan import STYLE
        assert STYLE.get("seaborn_palette") == "pastel"


class TestSetTheme:
    """Verify set_theme applies slidr styles and falls back to seaborn palettes."""

    def test_kcd_vietnam_applies_style(self):
        from slidr.render.seaborn import set_theme
        set_theme("kcd_vietnam")
        from slidr.render import seaborn
        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_kubecon_japan_applies_style(self):
        from slidr.render.seaborn import set_theme
        set_theme("kubecon_japan")
        from slidr.render import seaborn
        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_muted_is_palette_fallback(self):
        from slidr.render.seaborn import set_theme
        set_theme("muted")
        from slidr.render import seaborn
        assert seaborn._palette == "muted"
        assert seaborn._style is None

    def test_deep_is_palette_fallback(self):
        from slidr.render.seaborn import set_theme
        set_theme("deep")
        from slidr.render import seaborn
        assert seaborn._palette == "deep"

    def test_unknown_name_falls_back_to_palette(self):
        from slidr.render.seaborn import set_theme
        set_theme("nonexistent_style_xyz")
        from slidr.render import seaborn
        assert seaborn._palette == "nonexistent_style_xyz"

    def test_empty_string_defaults_to_pastel(self):
        from slidr.render.seaborn import set_theme
        set_theme("")
        from slidr.render import seaborn
        assert seaborn._palette == "pastel"

    def test_backward_compat_alias(self):
        from slidr.render.seaborn import set_palette, set_theme
        assert set_palette is set_theme
