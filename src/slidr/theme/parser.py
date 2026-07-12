"""Parse base.css + theme CSS with tinycss2 into PPTX styling rules."""

import tinycss2


def parse_theme(base_css: str, theme_css: str) -> dict:
    """Parse base.css + theme CSS into a flat style map for ODP rendering."""
    styles: dict[str, str] = {}
    _parse_sheet(base_css, styles)
    _parse_sheet(theme_css, styles)
    return _build_theme_dict(styles)


def parse_dark_theme(base_css: str, theme_css: str) -> dict:
    """Parse dark-mode CSS variables from [data-theme='dark'] blocks."""
    import tinycss2
    dark_css = ""
    for sheet in [base_css, theme_css]:
        rules = tinycss2.parse_stylesheet(sheet, skip_comments=True, skip_whitespace=True)
        in_dark = False
        for rule in rules:
            if rule.type != "qualified-rule":
                continue
            selector = tinycss2.serialize(rule.prelude).strip()
            if selector in ("[data-theme=\"dark\"]", "section[data-variant=\"dark\"]"):
                in_dark = True
                continue
            elif selector.startswith("[data-theme") or selector.startswith("section[data-variant"):
                in_dark = False
                continue
            if in_dark:
                # Check if this is still inside a dark block or the start of another
                pass
        # Simpler: just concatenate all declarations from dark-mode blocks
    # Simpler approach: extract -- variables from the dark blocks
    styles: dict[str, str] = {}
    _parse_sheet(base_css, styles)
    _parse_sheet(theme_css, styles)
    # Parse dark-specific CSS to get dark variable values
    _parse_dark_variables(base_css, theme_css, styles)
    return _build_theme_dict(styles)


def _parse_dark_variables(base_css: str, theme_css: str, styles: dict) -> None:
    """Extract dark mode CSS variables and override light mode values."""
    import tinycss2
    for sheet in [base_css, theme_css]:
        rules = tinycss2.parse_stylesheet(sheet, skip_comments=True, skip_whitespace=True)
        for rule in rules:
            if rule.type != "qualified-rule":
                continue
            selector = tinycss2.serialize(rule.prelude).strip()
            if selector not in ("[data-theme=\"dark\"]", "section[data-variant=\"dark\"]"):
                continue
            decls = tinycss2.parse_declaration_list(rule.content)
            for decl in decls:
                if decl.type != "declaration":
                    continue
                name = decl.name
                val = tinycss2.serialize(decl.value).strip()
                if name.startswith("--"):
                    styles[name] = val



    _parse_sheet(base_css, styles)
    _parse_sheet(theme_css, styles)
    # Also parse the dark mode overrides
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
                result[tag] = ["", ""]
            result[tag][0 if prop == "bg" else 1] = _resolve_color_var(val, styles)

    # From .tag-* selectors (fallback)
    for key, val in styles.items():
        m = re.match(r"tag_(\w+)_(border|background)", key)
        if m:
            tag, prop = m.group(1), m.group(2)
            if tag not in result:
                result[tag] = ["", ""]
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
        return {"padding": "section_padding", "font-family": "font_body_family", "text-align": "section_text_align", "font-size": "font_body_size"}.get(name)
    if selector == ".layout-title":
        return {"text-align": "title_text_align"}.get(name)
    if selector == "h1":
        return {"font-size": "font_h1_size"}.get(name)
    if selector == "h2":
        return {"font-size": "font_h2_size"}.get(name)
    if selector == "h3":
        return {"font-size": "font_h3_size"}.get(name)
    if selector == "code":
        return {"font-family": "font_code_family", "font-size": "font_code_size"}.get(name)
    if selector == ".quote":
        return {"font-size": "font_quote_size"}.get(name)
    if selector in ("p", "li"):
        return {"font-size": "font_li_size" if selector == "li" else "font_body_size"}.get(name)
    if selector == ".kicker":
        return {"font-size": "font_kicker_size"}.get(name)
    if selector == ".subtitle":
        return {"font-size": "font_subtitle_size"}.get(name)
    if selector == ".speaker":
        return {"font-size": "font_speaker_size"}.get(name)
    if selector == ".tiny":
        return {"font-size": "font_tiny_size"}.get(name)
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
    return parts[-1] if parts else ""


def _resolve_color_var(color: str, styles: dict) -> str:
    """Resolve var(--name) to its value from CSS variables."""
    import re
    m = re.match(r"var\((--[\w-]+)\)", color.strip())
    if m:
        return styles.get(m.group(1), color)
    return color



def _build_theme_dict(styles: dict) -> dict:
    ink = _to_rgb(styles.get("--ink", styles.get("--color-foreground", "")))
    return {
        "ink_rgb": ink,
        "ink_rgb_hex": _rgb_to_hex(ink),
        "muted_rgb": _to_rgb(styles.get("--muted", styles.get("--color-dimmed", ""))),
        "accent_rgb": _to_rgb(styles.get("--accent", styles.get("--color-accent", ""))),
        "font_body_family": styles.get("font_body_family", "Segoe UI"),
        "font_code_family": styles.get("font_code_family",
                                        styles.get("--font-mono", "SFMono-Regular")),
        "font_h1": _parse_size(styles.get("font_h1_size", ""), 63),
        "font_h2": _parse_size(styles.get("font_h2_size", ""), 36),
        "font_h3": _parse_size(styles.get("font_h3_size", ""), 18),
        "font_body": _parse_size(styles.get("font_body_size", ""), 18),
        "font_code": _parse_size(styles.get("font_code_size", ""), 14),
        "font_quote": _parse_size(styles.get("font_quote_size", ""), 24),
        "font_kicker": _parse_size(styles.get("font_kicker_size", ""), 14),
        "font_subtitle": _parse_size(styles.get("font_subtitle_size", ""), 32),
        "font_speaker": _parse_size(styles.get("font_speaker_size", ""), 18),
        "font_tiny": _parse_size(styles.get("font_tiny_size", ""), 13),
        "font_li": _parse_size(styles.get("font_li_size", ""), 16),
        "section_text_align": styles.get("section_text_align", "left"),
        "title_text_align": styles.get("title_text_align", "left"),
        "section_padding": _parse_padding(styles.get("section_padding", "")),
        "border_radius": styles.get("--radius", "0.4em"),
        "card_border_color": _resolve_color_var(
            _parse_border_color(styles.get("--card-border", "")),
            styles,
        ),
        "card_bg": styles.get("--color-card-bg", ""),
        "tag_colors": _extract_tag_colors(styles),
    }

def _rgb_to_hex(rgb: tuple) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
