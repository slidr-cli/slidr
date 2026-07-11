"""AST node types for slidr."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LayoutType(Enum):
    TITLE = "title"
    GRID2 = "grid-2"
    GRID3 = "grid-3"
    GRID4 = "grid-4"
    CONTENT = "content"


@dataclass
class Meta:
    theme: str = ""
    title: str = ""
    footer: str = ""
    paginate: bool = False
    size: str = "16:9"
    style: str = ""
    logo: str = ""
    pygments_style: str = "default"
    seaborn_theme: str = "muted"
    theme_variant: str = "light"

    def dimensions(self) -> tuple[int, int]:
        raw = str(self.size)
        if "x" in raw:
            w, h = raw.split("x")
            return (min(max(int(w), 320), 7680), min(max(int(h), 320), 7680))
        return {"16:9": (1280, 720), "4:3": (1024, 768), "16:10": (1280, 800)}.get(raw, (1280, 720))

    def physical_dims(self) -> tuple[float, float]:
        """Slide dimensions in mm for ODP/print."""
        raw = str(self.size)
        return {"16:9": (280.0, 157.5), "4:3": (280.0, 210.0),
                "16:10": (280.0, 175.0)}.get(raw, (280.0, 157.5))


@dataclass
class Document:
    meta: Meta
    slides: list["Slide"]


@dataclass
class Slide:
    layout: str = "content"
    children: list["Node"] = field(default_factory=list)
    notes: str = ""
    variant: str = ""


class Node:
    pass


@dataclass
class Heading(Node):
    level: int = 1
    content: list["Inline"] = field(default_factory=list)


@dataclass
class Paragraph(Node):
    content: list["Inline"] = field(default_factory=list)


@dataclass
class Grid(Node):
    cols: int = 2
    class_: str = ""
    children: list[Node] = field(default_factory=list)


@dataclass
class Card(Node):
    header: str = ""
    body: list[str] = field(default_factory=list)
    tag: Optional[str] = None
    class_: str = ""


@dataclass
class Arrow(Node):
    """Connector between two cards (arrow icon, label, etc.)."""
    content: str = ""


@dataclass
class Notes(Node):
    """Full-width conclusion card below a comparison layout."""
    content: str = ""
    tag: Optional[str] = None


@dataclass
class Row(Node):
    """Horizontal row of elements placed side by side."""
    children: list[Node] = field(default_factory=list)


@dataclass
class Table(Node):
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Quote(Node):
    content: list["Inline"] = field(default_factory=list)


@dataclass
class ListNode(Node):
    items: list[list[Inline]] = field(default_factory=list)


@dataclass
class AttrNode(Node):
    type: str = ""
    value: str = ""
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class CodeBlock(Node):
    content: str = ""
    language: str = ""


@dataclass
class Inline:
    pass


@dataclass
class Text(Inline):
    content: str = ""


@dataclass
class Strong(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass
class Emphasis(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass
class Strikethrough(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass
class CodeSpan(Inline):
    content: str = ""


@dataclass
class Image(Inline):
    src: str = ""
    alt: str = ""
    title: str = ""


@dataclass
class SoftBreak(Inline):
    pass
