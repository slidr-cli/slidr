"""AST node types for slidr."""

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

    def dimensions(self) -> tuple[int, int]:
        raw = str(self.size)
        if "x" in raw:
            w, h = raw.split("x")
            return (min(max(int(w), 320), 7680), min(max(int(h), 320), 7680))
        return {"16:9": (1280, 720), "4:3": (1024, 768), "16:10": (1280, 800)}.get(raw, (1280, 720))


@dataclass
class Document:
    meta: Meta
    slides: list["Slide"]


@dataclass
class Slide:
    layout: LayoutType = LayoutType.CONTENT
    children: list["Node"] = field(default_factory=list)
    notes: str = ""


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
class Table(Node):
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Quote(Node):
    content: list["Inline"] = field(default_factory=list)


@dataclass
class ListNode(Node):
    items: list[str] = field(default_factory=list)


@dataclass
class AttrNode(Node):
    type: str = ""
    value: str = ""
    attrs: dict[str, str] = field(default_factory=dict)


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
class CodeSpan(Inline):
    content: str = ""


@dataclass
class SoftBreak(Inline):
    pass
