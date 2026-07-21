"""Seaborn/matplotlib style for KubeCon Japan theme.

Based on seaborn's pastel defaults, with brand color overrides.

Primary accent: #3939D8 (blue)
Secondary accent: #DB1E3D (red)
Background: #ffffff
"""

from cycler import cycler

PALETTE = [
    "#8b8be0",  # pastel primary (from #3939D8)
    "#e0808e",  # pastel secondary (from #DB1E3D)
    "#7db87d",  # pastel green (from #2e7d32)
    "#a0b0c0",  # pastel dimmed (from #6a7a99)
    "#d8dce6",  # pastel border (from #c0c4d6)
    "#b0b0e8",  # pastel lighter blue (from #5b5bf0)
]

STYLE = {
    "seaborn_palette": "pastel",
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "Arial", "Helvetica Neue", "sans-serif"],
    "axes.prop_cycle": cycler(color=PALETTE),
    "axes.facecolor": "#f5f6fa",
    "axes.edgecolor": "#3939D8",
    "axes.labelcolor": "#2a2a5a",
    "axes.titlecolor": "#3939D8",
    "text.color": "#2a2a5a",
    "figure.facecolor": "#ffffff",
    "xtick.color": "#6a7a99",
    "ytick.color": "#6a7a99",
    "patch.edgecolor": "#DB1E3D",
    "patch.force_edgecolor": True,
}
