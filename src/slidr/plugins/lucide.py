"""markdown-it inline rule for lucide icons: {icon:star stroke=#64d039}"""

import re
from markdown_it.rules_inline import StateInline


_ICON_RE = re.compile(r'\{icon:(\S+)\s*([^}]*)\}')


def lucide_icon_inline(state: StateInline, silent: bool = False) -> bool:
    m = _ICON_RE.match(state.src[state.pos:])
    if not m:
        return False

    if not silent:
        name = m.group(1)
        rest = m.group(2).strip()
        attrs = {}
        for a in re.finditer(r'(\w+)="([^"]*)"', rest):
            attrs[a.group(1)] = a.group(2)
        for a in re.finditer(r'(\w+)=(\S+)', rest):
            if a.group(1) not in attrs:
                attrs[a.group(1)] = a.group(2)

        token = state.push("lucide_icon", "svg", 0)
        token.attrSet("name", name)
        for k, v in attrs.items():
            token.attrSet(k, v)

    state.pos += len(m.group(0))
    return True


def lucide_plugin(md):
    md.inline.ruler.before("image", "lucide_icon", lucide_icon_inline)
