"""Extract theme colors from CSS using tinycss2."""

import tinycss2


def parse_theme(css: str) -> dict[str, str]:
    """Extract CSS custom properties into a flat dict.
    Returns dict like {"--bg": "#07110c", "--ink": "#eef7f0", ...}
    """
    vars_: dict[str, str] = {}
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)

    for rule in rules:
        if rule.type != "qualified-rule":
            continue

        # Only process :root rules
        prelude = tinycss2.serialize(rule.prelude).strip()
        if prelude != ":root":
            continue

        # Parse declarations
        decls = tinycss2.parse_declaration_list(rule.content)
        for decl in decls:
            if decl.type == "declaration" and decl.name.startswith("--"):
                var_value = tinycss2.serialize(decl.value).strip()
                vars_[decl.name] = var_value

    return vars_


def to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a CSS color value to an (R, G, B) tuple."""
    value = value.strip()
    # #RRGGBB or #RGB
    if value.startswith("#"):
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        if len(value) == 6:
            return (
                int(value[0:2], 16),
                int(value[2:4], 16),
                int(value[4:6], 16),
            )
    # rgb(r, g, b) or rgba(r, g, b, a)
    if value.startswith("rgb"):
        import re
        m = re.findall(r"(\d+)", value)
        if len(m) >= 3:
            return (int(m[0]), int(m[1]), int(m[2]))

    return (0xFF, 0xFF, 0xFF)
