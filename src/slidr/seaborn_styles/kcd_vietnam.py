"""Seaborn/matplotlib style for KCD Vietnam theme.

Based on seaborn's pastel defaults, with brand color overrides.

Primary accent: #7A0504 (deep burgundy)
Secondary accent: #F1C560 (gold)
Card background: #F6ECD9 (warm cream)
Card stroke: #F1C560 (gold)
"""

from cycler import cycler

PALETTE = [
    "#c48787",  # pastel primary (from #7A0504)
    "#f5dfa0",  # pastel gold (from #F1C560)
    "#8fbc8f",  # pastel green (from #2e7d32)
    "#b0a090",  # pastel dimmed (from #7a6a5a)
    "#e8ded4",  # pastel border (from #d6c8b8)
    "#c9a0a0",  # pastel lighter red (from #c04040)
]

STYLE = {
    "seaborn_palette": "pastel",
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "Arial", "Helvetica Neue", "sans-serif"],
    "axes.prop_cycle": cycler(color=PALETTE),
    "axes.facecolor": "#F6ECD9",
    "axes.edgecolor": "#7A0504",
    "axes.labelcolor": "#3a2020",
    "axes.titlecolor": "#7A0504",
    "text.color": "#3a2020",
    "figure.facecolor": "#ffffff",
    "xtick.color": "#7a6a5a",
    "ytick.color": "#7a6a5a",
    "patch.edgecolor": "#F1C560",
    "patch.force_edgecolor": True,
}
