"""Seaborn code block execution for slide renderers.

Executes Python/seaborn code from fenced code blocks and returns the
generated plot. Two output modes:

- SVG string (for HTML inline -- scales with slide container)
- PNG file path (for ODP embedding)

Only active when seaborn + matplotlib are installed (pdm install -G plot).
Falls back to plain code highlighting otherwise.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path

_DEFAULT_FIGSIZE = (6.4, 4.8)
_DPI = 300
_TIMEOUT = 30


def _has_seaborn() -> bool:
    try:
        import seaborn  # noqa: F401
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


def render_seaborn_svg(content: str) -> str | None:
    """Execute seaborn code, return SVG string. None on failure."""
    if not _has_seaborn():
        return None
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False
    ) as script:
        script_path = script.name

    svg_path = script_path + ".svg"
    try:
        _write_seaborn_script(content, svg_path, script_path, fmt="svg")
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        if result.returncode == 0 and os.path.isfile(svg_path):
            return Path(svg_path).read_text()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(script_path)
        if os.path.isfile(svg_path):
            os.unlink(svg_path)


def render_seaborn_png(content: str) -> str | None:
    """Execute seaborn code, return path to generated PNG. Caller owns the temp file."""
    if not _has_seaborn():
        return None
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False
    ) as script:
        script_path = script.name

    png_path = script_path + ".png"
    try:
        _write_seaborn_script(content, png_path, script_path, fmt="png")
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        if result.returncode == 0 and os.path.isfile(png_path):
            return png_path
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(script_path)


def render_seaborn_datauri(content: str) -> str | None:
    """Execute seaborn code, return base64 SVG data URI. None on failure."""
    svg = render_seaborn_svg(content)
    if not svg:
        return None
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"


def _write_seaborn_script(
    content: str, out_path: str, script_path: str, fmt: str = "svg"
) -> None:
    wrapper = f'''
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

plt.figure(figsize={_DEFAULT_FIGSIZE!r})

{content}

plt.savefig({out_path!r}, format={fmt!r}, dpi={_DPI}, bbox_inches="tight")
plt.close("all")
'''
    Path(script_path).write_text(wrapper)
