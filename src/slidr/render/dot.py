"""Graphviz dot renderer for slidr.

Executes `dot` CLI to convert DOT language to SVG.
Font and colors come from CSS via tinycss2.

Falls back to code highlighting if dot is not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def render_dot_svg(content: str, font_family: str = "",
                   font_size: int = 14) -> str | None:
    """Render DOT code to SVG."""
    try:
        content = _preprocess(content, font_family, font_size)
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip():
            svg = result.stdout
            svg = _strip_xml_decl(svg)
            svg = _inject_theme_css(svg, font_family)
            return svg
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _preprocess(content: str, font_family: str, font_size: int) -> str:
    """Inject default font/size before any nodes if not already set."""
    if "fontsize" not in content and "fontname" not in content:
        fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
        size = font_size or 12
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "{" in line:
                indent = " " * (len(line) - len(line.lstrip()) + 4)
                defaults = (
                    f'{indent}node [fontname="{fam}" fontsize={size}];\n'
                    f'{indent}edge [fontname="{fam}" fontsize={size - 2}];'
                )
                lines[i] = lines[i] + "\n" + defaults
                break
        content = "\n".join(lines)
    return content


def _strip_xml_decl(svg: str) -> str:
    """Remove <?xml?> and <!DOCTYPE> from SVG for HTML embedding."""
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[-1].lstrip()
    if svg.startswith("<!DOCTYPE"):
        svg = svg.split(">", 1)[-1].lstrip()
    return svg


def _inject_theme_css(svg: str, font_family: str) -> str:
    """Inject a <style> block with slidr CSS variables matching .tag-* classes."""
    fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
    css = f"""\
    <style>
      .tag-default, .tag-default {{ fill: var(--color-card-bg); stroke: var(--color-card-bg); }}
      .tag-green {{ fill: var(--tag-green-bg); stroke: var(--tag-green-border); }}
      .tag-red   {{ fill: var(--tag-red-bg); stroke: var(--tag-red-border); }}
      .tag-cyan  {{ fill: var(--tag-cyan-bg); stroke: var(--tag-cyan-border); }}
      .tag-yellow {{ fill: var(--tag-yellow-bg); stroke: var(--tag-yellow-border); }}
      .node text {{ fill: var(--color-foreground); font-family: {fam}; }}
      .edge text {{ fill: var(--color-foreground); font-family: {fam}; }}
    </style>"""
    if "</svg>" in svg:
        svg = svg.replace("</svg>", f"{css}\n</svg>", 1)
    return svg
