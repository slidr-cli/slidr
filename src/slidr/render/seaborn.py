"""Seaborn code block execution for slide renderers.

Executes Python/seaborn code in-process from fenced code blocks and returns
SVG strings for both HTML inline and ODP embedding.

Only active when seaborn + matplotlib are installed (pdm install -G plot).
Falls back to plain code highlighting otherwise.

Theme support: the ``seaborn_theme`` frontmatter field accepts either a
seaborn palette name ("Paired", "deep", etc.) or a slidr theme name that
matches a CSS file in ``slidr/themes/<name>.css``. CSS variables are
parsed and mapped to matplotlib rcParams -- no hardcoded color duplication.
Style modules in ``slidr.seaborn_styles.<name>`` take precedence over CSS
and can set ``seaborn_palette`` to override the default ("Paired").
"""

import importlib
import io
import re
from pathlib import Path

_DEFAULT_FIGSIZE = (6.4, 4.8)
_DPI = 300
_DEFAULT_PALETTE = "Paired"
_THEME_DIR = Path(__file__).parent.parent / "themes"
_palette: str | None = None
_style: dict | None = None

# CSS variable → matplotlib rcParam(s)
_CSS_TO_RC = {
    "--color-card-bg": "axes.facecolor",
    "--color-accent-primary": ("axes.edgecolor", "axes.titlecolor"),
    "--color-accent-secondary": "patch.edgecolor",
    "--color-foreground": ("axes.labelcolor", "text.color"),
    "--color-background": "figure.facecolor",
    "--color-dimmed": ("xtick.color", "ytick.color"),
}


def _css_theme_rcparams(name: str) -> dict | None:
    """Parse a slidr CSS theme file into matplotlib rcParams. None if not found."""
    css_path = _THEME_DIR / f"{name}.css"
    if not css_path.is_file():
        return None
    raw = css_path.read_text()

    # Extract only :root block (light theme), not [data-theme="dark"]
    root_match = re.search(r":root\s*\{([^}]*)\}", raw, re.DOTALL)
    root_css = root_match.group(1) if root_match else raw

    vars_: dict[str, str] = {}
    for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", root_css):
        vars_[m.group(1)] = m.group(2).strip()

    font_match = re.search(r"section\s*\{([^}]*)\}", raw, re.DOTALL)
    font_css = font_match.group(1) if font_match else ""
    font_family = re.search(r"font-family:\s*([^;}]+)", font_css)
    font_stack = font_family.group(1).strip() if font_family else "sans-serif"
    fonts = [f.strip().strip('"') for f in font_stack.split(",")]

    style: dict = {
        "font.family": "sans-serif",
        "font.sans-serif": fonts,
        "patch.force_edgecolor": True,
    }
    for var, rc in _CSS_TO_RC.items():
        val = vars_.get(var)
        if val is None:
            continue
        if isinstance(rc, tuple):
            for r in rc:
                style[r] = val
        else:
            style[rc] = val
    return style


def set_theme(name: str) -> None:
    """Apply a seaborn palette or slidr style by name.

    Resolution order: slidr style module > CSS theme file > palette name.
    """
    global _palette, _style
    if not name:
        name = _DEFAULT_PALETTE
    try:
        # 1) style module (for custom overrides CSS can't express)
        mod = importlib.import_module(f"slidr.seaborn_styles.{name}")
        style = getattr(mod, "STYLE", {})
        if style:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns
            sns.set_theme(style="darkgrid", palette=style.pop("seaborn_palette", _DEFAULT_PALETTE))
            plt.rcParams.update(style)
            _style = style
            _palette = None
            return
    except ImportError:
        pass

    # 2) CSS theme file (single source of truth for brand colors)
    css_style = _css_theme_rcparams(name)
    if css_style:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        palette = css_style.pop("seaborn_palette", _DEFAULT_PALETTE)
        sns.set_theme(style="darkgrid", palette=palette)
        plt.rcParams.update(css_style)
        _style = css_style
        _palette = None
        return

    # 3) seaborn palette name
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
        sns.set_palette(_palette or _DEFAULT_PALETTE)
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
