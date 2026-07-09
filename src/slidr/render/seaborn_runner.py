"""Seaborn code block execution for slide renderers.

Executes Python/seaborn code in-process from fenced code blocks and returns
SVG strings for both HTML inline and ODP embedding.

Only active when seaborn + matplotlib are installed (pdm install -G plot).
Falls back to plain code highlighting otherwise.
"""

from __future__ import annotations

import io

_DEFAULT_FIGSIZE = (6.4, 4.8)
_DPI = 300
_palette: str | None = None


def set_palette(name: str) -> None:
    global _palette
    _palette = name


def render_seaborn_svg(content: str) -> str | None:
    """Execute seaborn code in-process, return SVG string. None on failure."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import numpy as np
    except ImportError:
        return None

    try:
        sns.set_palette(_palette or "muted")
        plt.figure(figsize=_DEFAULT_FIGSIZE)

        exec(content, {"sns": sns, "plt": plt, "pd": pd, "np": np})

        buf = io.BytesIO()
        plt.savefig(buf, format="svg", dpi=_DPI, bbox_inches="tight")
        plt.close("all")

        buf.seek(0)
        return buf.getvalue().decode("utf-8")
    except Exception:
        plt.close("all")
        return None
