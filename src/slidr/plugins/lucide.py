"""markdown-it inline rule for lucide icons: {icon:star stroke=#64d039}"""

import re
from markdown_it.rules_inline import StateInline


_ICON_RE = re.compile(r'\{icon:(\S+)\s*([^}]*)\}')


def render_icon(name: str, attrs: dict[str, str] | None = None) -> str:
    """Render a lucide icon to inline SVG. Shared by plugin and fenced preprocessor."""
    if not name:
        return ""
    try:
        from lucide import lucide_icon
        kwargs = dict(attrs or {})
        if "size" in kwargs:
            v = kwargs.pop("size")
            kwargs["height"] = kwargs["width"] = v
        has_explicit_size = "height" in kwargs or "width" in kwargs
        if not has_explicit_size:
            kwargs["height"] = "1em"
        svg = lucide_icon(name, **kwargs)
        if not has_explicit_size:
            svg = svg.replace('<svg', '<svg style="height:1em;width:auto;vertical-align:middle"', 1)
        return svg
    except Exception:
        return ""


def _parse_opts(opts: str) -> dict[str, str]:
    attrs = {}
    for a in re.finditer(r'(\w+)="([^"]*)"', opts):
        attrs[a.group(1)] = a.group(2)
    for a in re.finditer(r'(\w+)=(\S+)', opts):
        if a.group(1) not in attrs:
            attrs[a.group(1)] = a.group(2)
    return attrs


def lucide_icon_inline(state: StateInline, silent: bool = False) -> bool:
    m = _ICON_RE.match(state.src[state.pos:])
    if not m:
        return False

    if not silent:
        name = m.group(1)
        attrs = _parse_opts(m.group(2))
        token = state.push("lucide_icon", "svg", 0)
        token.attrSet("name", name)
        for k, v in attrs.items():
            token.attrSet(k, v)

    state.pos += len(m.group(0))
    return True


def lucide_plugin(md):
    md.inline.ruler.before("image", "lucide_icon", lucide_icon_inline)
