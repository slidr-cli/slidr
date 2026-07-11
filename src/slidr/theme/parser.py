"""Parse base.css + theme CSS with tinycss2 into PPTX styling rules."""

import tinycss2


def parse_theme(base_css: str, theme_css: str) -> dict:
    """Parse base.css + theme CSS into a flat style map for PPTX rendering.

    Returns dict with keys: ink_rgb, muted_rgb, accent_rgb, bg_color,
    font_h1, font_h2, font_h3, font_body, font_quote, font_small,
    section_padding, card_padding, card_radius
    """
    styles: dict[str, str] = {}
    _parse_sheet(base_css, styles)
    _parse_sheet(theme_css, styles)

    return {
        "ink_rgb": _to_rgb(styles.get("--ink", styles.get("color", "#333"))),
        "muted_rgb": _to_rgb(styles.get("--muted", "#777")),
        "accent_rgb": _to_rgb(styles.get("--accent", "#0288d1")),
        "font_body_family": styles.get("font_body_family", "Segoe UI"),
        "font_code_family": styles.get("font_code_family",
                                        styles.get("--font-mono", "SFMono-Regular")),
        "section_text_align": styles.get("section_text_align", "left"),
        "title_text_align": styles.get("title_text_align", "left"),
        "section_padding": _parse_padding(styles.get("section_padding", "")),
        "border_radius": styles.get("--radius", "0.4em"),
        "card_border_color": _resolve_color_var(
            _parse_border_color(styles.get("--card-border", "solid #ddd")),
            styles,
        ),
        "tag_colors": _extract_tag_colors(styles),
    }


def _extract_tag_colors(styles: dict) -> dict[str, tuple[str, str]]:
    """Extract per-tag fill and border colors from CSS .tag-* selectors."""
    import re
    result: dict[str, list[str]] = {}

    # From :root CSS variables
    for key, val in styles.items():
        m = re.match(r"--tag-(\w+)-(bg|border)", key)
        if m:
            tag, prop = m.group(1), m.group(2)
            if tag not in result:
                result[tag] = ["#e3f2fd", "#ddd"]
            result[tag][0 if prop == "bg" else 1] = _resolve_color_var(val, styles)

    # From .tag-* selectors (fallback)
    for key, val in styles.items():
        m = re.match(r"tag_(\w+)_(border|background)", key)
        if m:
            tag, prop = m.group(1), m.group(2)
            if tag not in result:
                result[tag] = ["#e3f2fd", "#ddd"]
            result[tag][0 if prop == "background" else 1] = val

    return {tag: (fill, border) for tag, (fill, border) in result.items()}


def _parse_sheet(css: str, styles: dict) -> None:
    """Parse a CSS string and extract relevant property values into styles dict."""
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)

    for rule in rules:
        if rule.type != "qualified-rule":
            continue

        selector = tinycss2.serialize(rule.prelude).strip()
        decls = tinycss2.parse_declaration_list(rule.content)

        for decl in decls:
            if decl.type != "declaration":
                continue
            name = decl.name
            val = tinycss2.serialize(decl.value).strip()

            # CSS variables
            if selector == ":root" and name.startswith("--"):
                styles[name] = val
                continue

            # Named selectors -> prefixed props
            if val.startswith("var("):
                continue
            key = _prop_for(name, selector)
            if key:
                styles[key] = val

            # Tag selectors (.tag-green, .tag-red, etc.)
            import re
            tm = re.match(r"\.tag-(\w+)", selector.strip())
            if tm and name in ("background", "border-color"):
                tag_key = f"tag_{tm.group(1)}_{'border' if name == 'border-color' else 'background'}"
                styles[tag_key] = val


def _prop_for(name: str, selector: str) -> str | None:
    """Map CSS properties needed by the ODP renderer to style keys."""
    if selector == "section":
        return {"padding": "section_padding", "font-family": "font_body_family", "text-align": "section_text_align"}.get(name)
    if selector == ".layout-title":
        return {"text-align": "title_text_align"}.get(name)
    if selector == "code":
        return {"font-family": "font_code_family"}.get(name)
    return None


def _to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        if len(value) == 6:
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    if value.startswith("rgb"):
        import re
        m = re.findall(r"\d+", value)
        if len(m) >= 3:
            return int(m[0]), int(m[1]), int(m[2])
    return 0x33, 0x33, 0x33


def _parse_size(value: str, default: int) -> int:
    """Parse a CSS size value to integer points."""
    if not value or value.startswith("var("):
        return default
    value = value.strip().rstrip(";")
    if value.endswith("px"):
        return int(float(value[:-2]))
    if value.endswith("pt"):
        return int(float(value[:-2]))
    if value.endswith("em"):
        return int(float(value[:-2]) * 18)
    return default


def _parse_padding(value: str) -> tuple[int, int, int, int]:
    """Parse CSS padding into (top, right, bottom, left) in px."""
    if not value:
        return (50, 64, 50, 64)
    parts = [p for p in value.split() if not p.startswith("var(")]
    if not parts:
        return (50, 64, 50, 64)
    vals = [int(float(p.rstrip("pxem;"))) for p in parts]
    if len(vals) == 1:
        return (vals[0], vals[0], vals[0], vals[0])
    if len(vals) == 2:
        return (vals[0], vals[1], vals[0], vals[1])
    if len(vals) == 4:
        return (vals[0], vals[1], vals[2], vals[3])
    return (50, 64, 50, 64)


def _parse_border_width(border: str) -> str:
    """Extract border width from CSS border shorthand (e.g. '1px solid #ddd')."""
    parts = border.split()
    return parts[0] if parts else "1px"


def _parse_border_color(border: str) -> str:
    """Extract border color from CSS border shorthand, after the style keyword."""
    parts = border.split()
    for i, p in enumerate(parts):
        if p in ("solid", "dashed", "dotted", "double", "none"):
            if i + 1 < len(parts):
                return parts[i + 1]
    return parts[-1] if parts else "#ddd"


def _resolve_color_var(color: str, styles: dict) -> str:
    """Resolve var(--name) to its value from CSS variables."""
    import re
    m = re.match(r"var\((--[\w-]+)\)", color.strip())
    if m:
        return styles.get(m.group(1), color)
    return color
