"""Directive parsing: @kicker, @speaker, @subtitle, etc. → AttrNode."""

import re
from slidr.parser.ast import AttrNode, Paragraph, Text, Node


def preprocess_directives(content: str) -> str:
    """Convert @directive lines to HTML comment markers."""
    lines = content.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@") and not stripped.startswith("@@") and " " in stripped:
            directive = stripped[1:].split(" ", 1)
            typ, value = directive[0], directive[1] if len(directive) > 1 else ""
            result.append(f"<!--attr:{typ}:{value}-->")
        else:
            result.append(line)
    return "\n".join(result)


def extract_attrs(nodes: list[Node]) -> list[Node]:
    """Post-process: convert attr comment markers to AttrNodes."""
    result = []
    for node in nodes:
        if isinstance(node, Paragraph) and len(node.content) == 1:
            text = node.content[0].content if isinstance(node.content[0], Text) else ""
            m = re.match(r"<!--attr:(\w+):(.*)-->", text)
            if m:
                typ, value = m.group(1), m.group(2)
                attrs = _parse_attrs(value)
                result.append(AttrNode(type=typ, value=value, attrs=attrs))
                continue
        result.append(node)
    return result


def parse_attr_token(html: str) -> AttrNode | None:
    """Parse a single <!--attr:...--> comment into an AttrNode."""
    m = re.match(r"<!--attr:(\w+):(.*)-->", html)
    if m:
        typ, value = m.group(1), m.group(2)
        return AttrNode(type=typ, value=value, attrs=_parse_attrs(value))
    return None


def _parse_attrs(value: str) -> dict[str, str]:
    """Parse key="val" and key=val patterns from a value string."""
    attrs = {}
    for ma in re.finditer(r'(\w+)="([^"]*)"', value):
        attrs[ma.group(1)] = ma.group(2)
    for ma in re.finditer(r'(\w+)=(\S+)', value):
        if ma.group(1) not in attrs:
            attrs[ma.group(1)] = ma.group(2)
    return attrs
