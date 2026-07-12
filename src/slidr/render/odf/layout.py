"""Layout context and height estimation for the ODP renderer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass
class LayoutContext:
    x: float = 0.0
    y: float = 0.0
    width: float = 24.0
    page_width: float = 28.0
    page_height: float = 15.75
    margin_left: float = 2.0
    margin_top: float = 2.0
    gap: float = 0.5
    source_dir: Path | None = None
    min_height: float = 0.0


def child_ctx(parent: LayoutContext, **overrides: Any) -> LayoutContext:
    return replace(parent, **overrides)


def estimate_text_height(text: str, font_size: int, width_cm: float) -> float:
    if not text:
        return 0.0
    width_pt = width_cm / 0.0353
    char_width_pt = font_size * 0.5
    chars_per_line = max(1, int(width_pt / char_width_pt))
    raw_lines = text.split("\n")
    total_lines = 0
    for line in raw_lines:
        if not line:
            total_lines += 1
        else:
            total_lines += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
    lines = max(1, total_lines)
    line_height_pt = font_size * 1.4
    return (lines * line_height_pt) * 0.0353


def estimate_elem_height(elem: Any, width_cm: float) -> float:
    from slidr.render.ir import Elem
    kind = elem.kind
    if kind in ("heading", "text", "quote", "code", "kicker", "subtitle", "tiny"):
        return estimate_text_height(elem.text, elem.font_size, width_cm) + 0.5
    elif kind == "list":
        h = 0.0
        for item in elem.items:
            h += estimate_text_height(item, elem.font_size, width_cm - 0.8) + 0.2
        return h + 0.5
    elif kind == "table":
        return 1.0 * (len(elem.rows) + 1) + 0.5
    elif kind == "grid":
        cols = elem.cols or len(elem.children) or 2
        if cols <= 0:
            cols = 1
        col_w = (width_cm - 0.5 * (cols - 1)) / cols
        total_h = 0.0
        for i in range(0, len(elem.children), cols):
            row_h = 0.0
            for child in elem.children[i : i + cols]:
                row_h = max(row_h, estimate_elem_height(child, col_w))
            total_h += row_h
        return total_h + 0.5
    elif kind == "card":
        h = 1.0 if elem.header else 0.0
        for line in elem.body:
            h += max(0.5, estimate_text_height(line, elem.font_size or 18, width_cm)) + 0.2
        return h + 0.5
    elif kind == "speaker":
        return (2.5 if elem.attrs.get("role") else 1.5) + 0.5
    return 0.5
