# Slidr Theme Guide

Slidr themes use CSS custom properties. Override them via frontmatter
`style:` block or by creating a new theme file.

## Theme structure

```
themes/default.css   →  colors, fonts, tag styles
templates/base.css   →  layout, spacing, screen/print modes
```

## CSS variables

All color values come from `:root` custom properties:

```css
:root {
  --color-background: #fff;        /* slide background */
  --color-foreground: #333;        /* text color */
  --color-dimmed: #777;            /* muted text, quotes, footers */
  --color-accent: #0288d1;         /* links, kicker, decorative borders */
  --color-accent-bg: rgba(2,136,209,0.1);  /* table header background */
  --color-border: #ddd;            /* table borders, card borders */
  --color-card-bg: #fafafa;        /* default card background */
  --color-background-stripe: #f5f5f5;  /* alternating table rows */

  /* Accent variants (default to --color-accent, themes can set independently) */
  --color-accent-primary: var(--color-accent);
  --color-accent-secondary: var(--color-accent);
  --color-accent-contrast: var(--color-accent);

  /* Tag colors */
  --tag-green-bg: #e8f5e9;         --tag-green-border: #0fd05d;
  --tag-cyan-bg: #e0f7fa;          --tag-cyan-border: #67d8ff;
  --tag-yellow-bg: #fff9c4;        --tag-yellow-border: #ffd166;
  --tag-red-bg: #ffebee;           --tag-red-border: #ff7a7a;
}
```

### Background and watermark

Slide background image and watermark are controlled via variables in `base.css`.
Themes set them; frontmatter `style:` overrides them.

```css
:root {
  --bg-image: none;        /* slide background image */
  --bg-overlay: transparent; /* color overlay on bg image */
  --watermark: none;       /* bottom-right brand mark */
}
```

The background is applied as:
```css
section {
  background: linear-gradient(var(--bg-overlay), var(--bg-overlay)), var(--bg-image) left top / cover no-repeat;
}
```

The watermark uses `section::after` (positioned bottom-right in `base.css`).
Set `--watermark: url(...)` in a theme or frontmatter to activate it.

### Logo and dark logo

Frontmatter fields for top-right logo with dark mode variant:

```yaml
---
logo: assets/logo.svg
logo_dark: assets/logo-white.png
---
```

`logo:` sets `--logo` CSS variable. `logo_dark:` sets `--logo-dark`.
The positioning and sizing live in `base.css` via `section::before`.
Dark mode and `.layout-title` use `--logo-dark` automatically.

### Accent classes

Three utility classes for referencing accent colors without hardcoded hex values:

```css
.accent-primary   { color: var(--color-accent-primary);   fill: var(--color-accent-primary);   stroke: var(--color-accent-primary); }
.accent-secondary { color: var(--color-accent-secondary); fill: var(--color-accent-secondary); stroke: var(--color-accent-secondary); }
.accent-contrast  { color: var(--color-accent-contrast);  fill: var(--color-accent-contrast);  stroke: var(--color-accent-contrast); }
```

All three default to `--color-accent`. A theme sets them independently for distinct
positive/negative/warning colors. The classes set `color`, `fill`, and `stroke`
so they work for text, filled shapes, and lucide icons:

```markdown
{icon:check cls=accent-primary}     # success
{icon:x cls=accent-secondary}       # failure
{icon:alert cls=accent-contrast}    # warning
```

### Speaker with social links

`@speaker` renders name, role, and optional contact icons with text labels:

```markdown
@speaker name="Jane Doe" role="Engineer"
  github=github.com/jane twitter=@jane email=jane@example.com
  linkedin=linkedin.com/in/jane website=jane.dev
```

Supported fields: `github`, `twitter`, `email`, `linkedin`, `website`.
Each renders as a lucide icon + link below the name/role.
Multiple `@speaker` directives stack vertically.

### Theme override pattern

Themes set CSS variables; `base.css` defines structure that references them.
`kubecon_japan.css` demonstrates the pattern:

```css
:root {
  --bg-overlay: rgba(255,255,255,0.94);  /* white wash over bg */
  --watermark: url(brand/cncf_logo.svg);  /* bottom-right mark */
  --logo-dark: url(brand/logo-white.png); /* dark-mode logo */
}
.layout-title { --logo: var(--logo-dark); }  /* title always dark */
section::after { opacity: 0.15; }            /* watermark subtlety */
```

Everything that can vary has a variable. List font size:

```css
li { font-size: 0.9em; }
```

Maps to `font_li_size` for ODP. Override in `style:`:

```yaml
style: |
  li { font-size: 1em; }
```

Bullet list marker via `--list-style`. Default is `"\\25B8  "` (▸ triangle).
Change to standard bullets or custom characters:

```yaml
style: |
  :root { --list-style: disc; }
```

## Dark mode

Dark mode uses CSS variables scoped under `[data-theme="dark"]`. Two triggers:

**Global** (every slide):

```yaml
---
variant: dark
---
```

This sets `data-theme="dark"` on the `<html>` element. All slides inherit dark
variables.

**Per-slide** (toggle mid-presentation):

```markdown
@variant dark

## This slide is dark

@variant light

## Back to light
```

Sets `data-theme="dark"` on the `<section>` element. Only that slide goes dark.
The next `@variant light` switches back.

**Theme implementation**:

```css
[data-theme="dark"] {
  --color-background: #1a1a2e;
  --color-foreground: #e0e0e0;
  --color-dimmed: #999;
  --color-accent: #58a6ff;
  --color-card-bg: #161b22;
  ...
}

section[data-theme="dark"] {
  --color-background: #1a1a2e;
}
```

Use `[data-theme="dark"]` for global overrides (applied to `<html>`).
Use `section[data-theme="dark"]` for per-slide overrides.
Both selectors work in the same theme file.

## Logo

The logo renders via `section::before` with `position: absolute` at the top-right
corner. Two ways to set it:

**Frontmatter** (per-presentation, overrides theme):

```yaml
---
logo: assets/my-logo.svg
---
```

The `logo:` field generates its own `section::before` rule that appears after the
theme CSS in the stylesheet, so it naturally overrides any theme default logo.

**Theme** (default logo for all presentations using the theme):

```css
section::before {
  content: "";
  position: absolute;
  top: 4%;
  right: 5%;
  width: 14%;
  height: 0;
  padding-bottom: 6%;
  background: url("brand/logo.svg") center / contain no-repeat;
  opacity: 0.92;
}
[data-theme="dark"] section::before {
  background-image: url("brand/logo-white.png");
}
```

Both use the same selector -- the one appearing last in the stylesheet wins.
Theme CSS is injected first, then `logo:` CSS, then `style:` CSS.

## Overriding via frontmatter

The `style:` block in frontmatter is injected directly into the HTML `<style>` tag.
Override any CSS variable or add custom rules:

```yaml
---
style: |
  :root {
    --color-accent: #e91e63;
    --color-card-bg: #fce4ec;
  }
  h1 { font-size: 3em; }
---
```

## Custom theme file

Create `themes/my-theme.css`, then use it:

```yaml
---
theme: my-theme
---
```

Your theme only needs to set the variables you want to change.
The rest fall back to `default.css`.

```css
/* themes/my-theme.css */
:root {
  --color-background: #0d1117;
  --color-foreground: #c9d1d9;
  --color-accent: #58a6ff;
  --color-card-bg: #161b22;
}
```

## Global layout variables

These are in `base.css` and control spacing:

```css
:root {
  --radius: 0.4em;            /* border radius for cards, code, notes */
  --gap: 1em;                 /* grid gap, layout column gap */
  --font-mono: "SFMono-Regular", Consolas, monospace;
  --section-padding-v: 2.8em; /* vertical slide padding */
  --section-padding-h: 3.6em; /* horizontal slide padding */
  --card-border: 1px solid var(--color-border);
  --title-h1-size: 3.5em;     /* title slide h1 font size */
  --title-subtitle-size: 1.8em; /* title slide subtitle font size */
}
```

## Slide layouts

Predefined layouts activated via `@layout <name>` at the top of a slide:

| Layout | Description |
|--------|-------------|
| `image-right` | Text in left column, image in right column |
| `image-left` | Image in left column, text in right column |
| `two-col` | Two equal text columns, split at `@col` |
| `compare` | Card → arrow → card, with optional `::: notes` footer |
| `ecosystem` | Compact stacked content for logo grids, partner slides |

### Ecosystem layout

Designed for partner/ecosystem slides with logo grids and metrics:

```markdown
@layout ecosystem

## Ecosystem

### Open Source, CNCF Backed

::: grid {cols=2}
::: card {metric}
3.1k
Github Stars
:::
...
:::

### Ecosystem & Device Support

::: card
![NVIDIA](ecosystem/devices/nvidia.png) ...
:::
```

Styling applied automatically:
- `h3` labels: `0.7em`, no underline -- acts as row label above cards
- Cards: `0.3em 0.5em` compact padding
- Card `<p>` with only images: `display: contents` so images flow inline and wrap naturally
- Logo images: uniform `0.8em × 0.8em`, `object-fit: contain`
- Natural content stacking -- no IR row splitting needed

## What the ODP renderer reads from CSS

The ODP renderer extracts these via tinycss2:

| CSS | ODP use |
|-----|---------|
| `section { font-family }` | body font |
| `code { font-family }` | mono font |
| `section { text-align }` | default text alignment |
| `.layout-title { text-align }` | title slide alignment |
| `.tag-green { background, border-color }` | card fill + border |
| `--radius` | frame corner radius |
| `--card-border` | card border color |
