"""Seaborn code block execution for slide renderers.

Executes Python/seaborn code in-process from fenced code blocks and returns
SVG strings for both HTML inline and ODP embedding.

Only active when seaborn + matplotlib are installed (pdm install -G plot).
Falls back to plain code highlighting otherwise.

Theme support: the ``seaborn_theme`` frontmatter field accepts either a
seaborn palette name ("muted", "deep", etc.) or a slidr seaborn style name
that matches a module in ``slidr.seaborn_styles.<name>``. Style modules
export a STYLE dict of matplotlib rcParams.
"""

import importlib
import io

_DEFAULT_FIGSIZE = (6.4, 4.8)
_DPI = 300
_palette: str | None = None
_style: dict | None = None


def set_theme(name: str) -> None:
    """Apply a seaborn palette or slidr style by name.

    If *name* matches a module in ``slidr.seaborn_styles``, the module's
    STYLE dict is applied via ``plt.rcParams.update``. Otherwise *name* is
    treated as a seaborn palette name.
    """
    global _palette, _style
    if not name:
        name = "pastel"
    try:
        mod = importlib.import_module(f"slidr.seaborn_styles.{name}")
        style = getattr(mod, "STYLE", {})
        if style:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns
            sns.set_theme(style="darkgrid", palette=style.pop("seaborn_palette", "pastel"))
            plt.rcParams.update(style)
            _style = style
            _palette = None
            return
    except ImportError:
        pass
    _palette = name
    _style = None


# backward compat alias
set_palette = set_theme


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
        if _style is not None:
            plt.rcParams.update(_style)
        sns.set_palette(_palette or "pastel")
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
