"""Seaborn code block execution for slide renderers.

Executes Python/seaborn code from fenced code blocks and returns the
generated image as either a file path (for ODP embedding) or a base64
data URI (for HTML inline).

Only active when seaborn + matplotlib are installed (pdm install -G plot).
Falls back to plain code highlighting otherwise.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path


def _has_seaborn() -> bool:
    try:
        import seaborn  # noqa: F401
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


def render_seaborn_image(content: str) -> str | None:
    """Execute seaborn code, return path to generated PNG. None on failure."""
    if not _has_seaborn():
        return None
    with (
        tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False
        ) as script,
        tempfile.NamedTemporaryFile(
            suffix=".png", delete=False
        ) as img,
    ):
        script_path = script.name
        img_path = img.name

    try:
        _write_seaborn_script(content, img_path, script_path)
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and os.path.isfile(img_path):
            return img_path
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(script_path)


def render_seaborn_datauri(content: str) -> str | None:
    """Execute seaborn code, return base64 data URI. None on failure."""
    img_path = render_seaborn_image(content)
    if not img_path:
        return None
    try:
        with open(img_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except OSError:
        return None
    finally:
        os.unlink(img_path)


def _write_seaborn_script(
    content: str, img_path: str, script_path: str
) -> None:
    """Write a Python script that runs the user's seaborn code and saves the figure."""
    wrapper = f'''
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

{content}

plt.savefig({img_path!r}, dpi=150, bbox_inches="tight")
plt.close("all")
'''
    Path(script_path).write_text(wrapper)
