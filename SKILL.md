# Slidr slide creation

Create markdown presentations for slidr (markdown to styled HTML slides with PDF output).

## Quick start

Generate a `.md` file and build with `pdm run slidr file.md`. Slides are separated
by `---` on its own line. The first YAML frontmatter block sets global options.

## Frontmatter

```yaml
---
theme: default
title: My Talk
footer: "Conference 2026"
paginate: true
size: 16:9              # 16:9 | 4:3 | 16:10
logo: ./logo.png
pygments_style: monokai # any style from pygments-styles.org
style: |
  .custom { color: red; }
---
```

## Slide directives

Place directives on their own line at the top of a slide body:

| Directive | Effect |
|-----------|--------|
| `@kicker text` | Title slide eyebrow, monospace accent |
| `@subtitle text` | Title slide subtitle |
| `@speaker name=X role=Y` | Title slide attribution with optional role |
| `@layout name` | Apply slide layout (see below) |
| `@col` | Explicit column break within `two-col` layout |
| `@tiny text` | Small dimmed annotation |

## Layouts

Auto-detected: `title` (has h1/kicker/speaker), `grid-2/3/4` (has grid), `content` (default).

Explicit via `@layout`:

| Layout | Behavior |
|--------|----------|
| `@layout two-col` | Heading full-width, body split 50/50. Use `@col` to control split point. |
| `@layout image-right` | Heading full-width, text left, image right |
| `@layout image-left` | Heading full-width, image left, text right |

Custom layouts: `@layout <name>` adds CSS class `layout-<name>`, style via `style:` frontmatter.

## Block syntax

```
::: grid {cols=2}           # auto-detected as grid-2 layout
::: card                     # basic card with border-radius
::: card{ tag="green" }      # colored left border: green, cyan, yellow, red
> quote text                 # blockquote, renders as .quote div
| col1 | col2 | col3 |       # pipe table with header row
`inline code`                # inline code span
```language                  # fenced code block, syntax highlighted
:::
```

## Speaker notes

HTML comments at the top of a slide are notes visible in the presenter view:

```markdown
---

<!--
Points to cover:
- Architecture overview
- Performance numbers
-->
```

## Title slide pattern

```markdown
@kicker v1.0 · Date

# Talk Title

@subtitle Optional subtitle

@speaker name="Author" role="Affiliation"
```

## Card grid pattern

```markdown
## Section Title

::: grid {cols=3}
::: card{ tag="green" }
### Card Title
Body text for this card.
:::

::: card{ tag="cyan" }
### Another Card
More content here.
:::

::: card{ tag="yellow" }
### Third Card
Additional information.
:::
:::
```

## Two-column with explicit split

```markdown
@layout two-col

## Title

- Item group one
- More items here

@col

- Item group two
- Additional items
```

## Image layout pattern

```markdown
@layout image-right

## Title

Descriptive text about the topic goes here. Can include multiple paragraphs.

- Bullet points
- Supporting details

![](path/to/image.png)
```

## Table with quote

```markdown
## Table Title

| Header A | Header B | Header C |
|----------|----------|----------|
| data     | data     | data     |

> Key insight or callout about this data
```

## Theme creation

Create a `.css` file with CSS custom properties and visual rules. The theme is
loaded after `base.css` (which handles layout, positioning, spacing). Themes
should only define colors, fonts, and visual decoration.

### Theme template

```css
/* Theme name */

:root {
  --color-background: #fff;
  --color-background-stripe: #f5f5f5;
  --color-foreground: #333;
  --color-dimmed: #777;
  --color-accent: #0288d1;
  --color-accent-bg: rgba(2, 136, 209, 0.1);
  --color-border: #ddd;
}

section {
  background: var(--color-background);
  color: var(--color-foreground);
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

h1, h2, h3, h4, h5, h6 { color: var(--color-foreground); }
h1 { font-size: 2.5em; }
h2 { font-size: 1.8em; }
h3 { font-size: 1.3em; }

code { background: rgba(0,0,0,0.05); font-family: monospace; }
pre { background: rgba(0,0,0,0.05); }

blockquote { border-left-color: var(--color-accent); color: var(--color-dimmed); }
th { background: var(--color-accent-bg); color: var(--color-foreground); }
th, td { border: 1px solid var(--color-border); }
tr:nth-child(even) { background: var(--color-background-stripe); }

a { color: var(--color-accent); }
.card { background: rgba(0,0,0,0.15); border: 1px solid var(--color-border); }
.quote { border-left-color: var(--color-accent); }
.kicker { color: var(--color-accent); }
.speaker .role { color: var(--color-dimmed); }
footer, .slide-num { color: var(--color-dimmed); }
.subtitle, .tiny, .muted { color: var(--color-dimmed); }

.tag-green { border-color: #0fd05d; }
.tag-cyan  { border-color: #67d8ff; }
.tag-yellow { border-color: #ffd166; }
.tag-red   { border-color: #ff7a7a; }
```

Apply via: `pdm run slidr slides.md --theme ./my-theme.css` or reference by filename
in frontmatter: `theme: my-theme`.

## Reference

See `examples/features_demo.md` for a complete 10-slide deck exercising all features.
See `src/slidr/themes/default.css` for the default theme structure.
