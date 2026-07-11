"""Graphviz dot renderer for slidr.

Executes `dot` CLI to convert DOT language to SVG.
Font and colors come from CSS via tinycss2.

Falls back to code highlighting if dot is not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def render_dot_svg(content: str, font_family: str = "",
                   font_size: int = 14,
                   tag_colors: dict[str, tuple[str, str]] | None = None) -> str | None:
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
            svg = _inject_theme_css(svg, font_family, tag_colors)
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
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[-1].lstrip()
    if svg.startswith("<!DOCTYPE"):
        svg = svg.split(">", 1)[-1].lstrip()
    return svg


def _inject_theme_css(svg: str, font_family: str,
                      tag_colors: dict[str, tuple[str, str]] | None) -> str:
    """Inject a <style> block with colors from CSS theme."""
    fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
    tags = tag_colors or {}
    default_fill = tags.get("default", ("#fafafa", "#ddd"))[0]
    default_stroke = tags.get("default", ("#fafafa", "#ddd"))[1]
    green = tags.get("green", ("#e8f5e9", "#0fd05d"))
    red = tags.get("red", ("#ffebee", "#ff7a7a"))
    cyan = tags.get("cyan", ("#e0f7fa", "#67d8ff"))
    yellow = tags.get("yellow", ("#fff9c4", "#ffd166"))
    fg = "#333"

    css = f"""\
    <style>
      .node > polygon, .graph polygon {{ fill: {default_fill}; stroke: {default_stroke}; stroke-linejoin: round; }}
      .node.green > polygon   {{ fill: {green[0]}; stroke: {green[1]}; stroke-linejoin: round; }}
      .node.red > polygon     {{ fill: {red[0]}; stroke: {red[1]}; stroke-linejoin: round; }}
      .node.cyan > polygon    {{ fill: {cyan[0]}; stroke: {cyan[1]}; stroke-linejoin: round; }}
      .node.yellow > polygon  {{ fill: {yellow[0]}; stroke: {yellow[1]}; stroke-linejoin: round; }}
      .graph title {{ stroke: {default_stroke}; }}
      .cluster > text {{ fill: {fg}; font-family: {fam}; }}
      .edge > path, .edge > polygon {{ stroke: {fg}; }}
      .cluster polygon {{ stroke: none; }}
      .node text {{ fill: {fg}; font-family: {fam}; }}
      .edge text {{ fill: {fg}; font-family: {fam}; }}
    </style>"""
    if "</svg>" in svg:
        svg = svg.replace("</svg>", f"{css}\n</svg>", 1)
    return svg
