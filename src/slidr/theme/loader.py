"""Theme loader -- raw CSS passthrough with variable extraction."""

import re
from dataclasses import dataclass, field


@dataclass
class Theme:
    raw: str
    vars: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> str:
        return self.vars.get(name, "")


def load(raw_css: str) -> Theme:
    """Parse raw CSS and extract CSS variables."""
    theme = Theme(raw=raw_css)
    # Extract --name: value; patterns
    for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", raw_css):
        theme.vars[m.group(1)] = m.group(2).strip()
    return theme
