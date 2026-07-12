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

  /* Tag colors */
  --tag-green-bg: #e8f5e9;         --tag-green-border: #0fd05d;
  --tag-cyan-bg: #e0f7fa;          --tag-cyan-border: #67d8ff;
  --tag-yellow-bg: #fff9c4;        --tag-yellow-border: #ffd166;
  --tag-red-bg: #ffebee;           --tag-red-border: #ff7a7a;
}
```

## Dark mode

Set `variant: dark` in frontmatter:

```yaml
---
title: My Talk
variant: dark
---
```

Or toggle per-slide:

```markdown
@variant dark

## This slide is dark
```

Dark mode overrides the same variables:

```css
section[data-variant="dark"] {
  --color-background: #1a1a2e;
  ...
}
```

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
}
```

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
