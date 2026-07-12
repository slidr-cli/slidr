"""ODF style registries for the ODP renderer."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from odfdo import Document, Style


@dataclass(frozen=True)
class StyleKey:
    font_size: int = 0
    color: str = ""
    font_weight: str = ""
    font_style: str = ""
    font_family: str = ""
    fill: str = ""
    text_align: str = ""
    padding: str = ""
    border_radius: str = ""
    border_color: str = ""
    border_width: str = ""


@dataclass(frozen=True)
class TextStyleKey:
    weight: str = "normal"
    font_style: str = "normal"
    font_family: str = ""
    font_size: int = 0


class GraphicStyleRegistry:
    def __init__(self) -> None:
        self._styles: dict[StyleKey, str] = {}
        self._counter = count(1)

    def register(self, key: StyleKey) -> str:
        if key not in self._styles:
            self._styles[key] = f"SlidrG_{next(self._counter):03d}"
        return self._styles[key]

    def insert_all(self, document: Document) -> None:
        for key, name in self._styles.items():
            kwargs: dict[str, str] = {}
            if key.fill:
                kwargs["fill_color"] = key.fill
            else:
                kwargs["draw:fill"] = "none"
            style = Style(
                "graphic",
                name=name,
                stroke="none",
                padding_top=key.padding,
                padding_bottom=key.padding,
                padding_left=key.padding,
                padding_right=key.padding,
                **kwargs,
            )
            style.set_properties(area="paragraph", text_align=key.text_align)
            style.set_properties(
                area="text",
                color=key.color,
                font=key.font_family,
                font_family=key.font_family,
                size=f"{key.font_size}pt",
                weight=key.font_weight,
                font_style=key.font_style,
            )
            if key.border_radius:
                props = style.get_element("style:graphic-properties")
                if props is not None:
                    props.set_attribute("draw:corner-radius", key.border_radius)
            if key.border_color:
                props = style.get_element("style:graphic-properties")
                if props is not None:
                    props.set_attribute("draw:stroke", "solid")
                    props.set_attribute("svg:stroke-color", key.border_color)
                    props.set_attribute("svg:stroke-width", key.border_width or "0.01mm")
            document.insert_style(style)


class TextStyleRegistry:
    def __init__(self) -> None:
        self._styles: dict[TextStyleKey, str] = {}
        self._counter = count(1)

    def register(self, key: TextStyleKey) -> str:
        if key not in self._styles:
            self._styles[key] = f"SlidrT_{next(self._counter):03d}"
        return self._styles[key]

    def insert_all(self, document: Document) -> None:
        for key, name in self._styles.items():
            style = Style(
                "text",
                name=name,
                bold=(key.weight == "bold"),
                italic=(key.font_style == "italic"),
            )
            if key.font_family:
                style.set_properties(area="text", font=key.font_family)
            if key.font_size:
                style.set_properties(area="text", size=f"{key.font_size}pt")
            document.insert_style(style)


# Module-level globals set by init
_FONT_SANS = ""
_FONT_MONO = ""
_BORDER_RADIUS = ""
_BORDER_COLOR = ""
_TEXT_ALIGN = "left"
_FONT_SCALE = 1.0

_TAG_COLORS: dict[str, str] = {}
_TAG_BORDERS: dict[str, str] = {}


def set_fonts(sans: str, mono: str) -> None:
    global _FONT_SANS, _FONT_MONO
    _FONT_SANS = sans.split(",")[0].strip().strip('"') if sans else ""
    _FONT_MONO = mono.split(",")[0].strip().strip('"') if mono else ""


def set_border_radius(radius: str) -> None:
    global _BORDER_RADIUS
    _BORDER_RADIUS = radius


def set_border_color(color: str) -> None:
    global _BORDER_COLOR
    _BORDER_COLOR = color


def set_tag_colors(colors: dict[str, tuple[str, str]]) -> None:
    global _TAG_COLORS, _TAG_BORDERS
    _TAG_COLORS = {tag: fill for tag, (fill, _) in colors.items()}
    _TAG_BORDERS = {tag: border for tag, (_, border) in colors.items()}
    if "" not in _TAG_COLORS:
        first = next(iter(_TAG_COLORS.values()), "")
        _TAG_COLORS[""] = first


def tag_fill(tag: str) -> str:
    return _TAG_COLORS.get(tag, _TAG_COLORS.get("", ""))


def tag_border(tag: str) -> str:
    return _TAG_BORDERS.get(tag, _BORDER_COLOR)


def create_table_styles(document: Document, styles: dict) -> tuple[str, str]:
    """Create ODF table and table-cell styles from CSS theme values."""
    from odfdo.style import create_table_cell_style

    border_color = styles.get("card_border_color", "")
    cell_padding = styles.get("section_padding", "")
    # Default to 0.1cm if no CSS padding found
    padding = "0.1cm"

    cell_name = "SlidrTableCell"
    table_name = "SlidrTable"

    cell_style = create_table_cell_style(
        border=f"0.06pt solid {border_color}",
        padding=padding,
    )
    cell_style.name = cell_name
    document.insert_style(cell_style)

    table_style = Style("table", name=table_name)
    from odfdo.element import Element
    props = Element.from_tag("style:table-properties")
    table_style.append(props)
    document.insert_style(table_style)

    return table_name, cell_name
