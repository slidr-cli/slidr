# Slidr

Markdown to styled PPTX + PDF. Layout primitives (cards, grids, tables) with CSS theming. Python + markdown-it.

## Install

```bash
pdm install
```

## Quick start

```bash
pdm run slidr slides.md          # → dist/slides.html
pdm run slidr slides.md --debug  # dump parsed AST
```

Output goes to `<input_dir>/dist/` by default. Assets are copied alongside.

## Slide structure

A slidr deck is a markdown file with YAML frontmatter. Slides are separated by `---`.

```markdown
---
theme: default
title: My Presentation
footer: "Conf 2026"
size: 16:9
style: |
  :root { --accent: #0fd05d; }
---

@kicker Conference Talk

# My Title

@subtitle A subtitle here

@speaker name=Jane role=Engineer

---

## Agenda

::: card
### Topic One
Description here.
:::

::: card
### Topic Two
More description.
:::

::: card
### Topic Three
More description.
:::

> A blockquote with important context.

---

## Data

| Column | Value |
|--------|-------|
| A      | 1     |
| B      | 2     |
```

## Cards

Cards are the primary content container. Each card has a heading (`### Header`) and body text.

**Syntax:**

```markdown
::: card
### Header
Body text. Multiple paragraphs supported.
:::
```

**Auto-grouping:** two or more consecutive cards automatically form a grid. Column count matches the number of cards.

```markdown
::: card
### Left
Content.
:::

::: card
### Right
Content.
:::
```
→ Renders as a 2-column grid. No `::: grid` wrapper needed.

## Grids

Explicit grids are only needed when you want to override the default behavior: custom column count, CSS class, or a different number of columns than the card count.

```markdown
::: grid {cols=3, class="compact-grid"}
::: card
### Card 1
:::
::: card
### Card 2
:::
::: card
### Card 3
:::
:::
```

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `cols=N` | Column count (default: auto from card count) |
| `class="name"` | Additional CSS class |
| Bare words | Shorthand for CSS class: `::: grid {road-grid}` |

**Grid variant classes** (from theme CSS):

| Class | Typical cols | Use |
|-------|-------------|-----|
| `compact-grid` | 3 | Dense card layout |
| `road-grid` | 4 | Four-column feature grid |
| `evidence-grid` | 2 | Wide evidence cards |
| `end-grid` | 2 | Closing section cards |
| `end-links` | 3 | Link cards at end |
| `mt-grid` | 2 | Grid with top margin |

## Directives

Single-line annotations using `@type` syntax.

| Directive | Renders as |
|-----------|-----------|
| `@kicker text` | `<div class="kicker">` |
| `@subtitle text` | `<p class="subtitle">` |
| `@speaker name=X role=Y` | `<div class="speaker"><span>` |
| `@tiny text` | `<p class="tiny">` |
| `@muted text` | `<p class="muted">` |

Custom types render generically: `@custom-badge label=NEW text` → `<div class="custom-badge" data-label="NEW">text</div>`.

## Tables

Standard markdown pipe tables (GFM):

```markdown
| Header | Header |
|--------|--------|
| Cell   | Cell   |
```

## Blockquotes

```markdown
> Important quote or callout text.
```

## Speaker notes

HTML comments at the start of a slide become speaker notes:

```markdown
---

<!--
These are speaker notes.
Only visible in presenter mode.
-->

## Slide Title
```

## Frontmatter

```yaml
theme: default       # theme name
title: "..."         # document title
footer: "..."        # slide footer
paginate: true       # show page numbers
size: 16:9           # 16:9 (1280x720), 4:3 (1024x768), 16:10 (1280x800), or "1920x1080"
style: |             # raw CSS injected into output (overrides defaults)
  .card { border-color: red; }
logo: ./assets/brand/logo.png  # logo on every slide
```

## Styling

CSS is written directly in the `style:` frontmatter block. No CSS parser — it's injected raw into the HTML and handled by the browser.

```yaml
style: |
  :root {
    --bg: #111;
    --ink: #eee;
    --accent: #0fd05d;
  }
  section {
    background: var(--bg);
    color: var(--ink);
    padding: 2.78em 3.56em;
  }
  .card {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--accent);
  }
  .quote {
    border-left: 0.25em solid var(--accent);
  }
```

Base font-size is 18pt on `section`. Use `em` units for spacing.

## Marp migration

1. Remove `marp: true` and `description:` from frontmatter
2. Convert HTML divs:
   - `<div class="grid">` → remove wrapper (cards auto-group)
   - `<div class="card">` → `::: card`
   - `<div class="quote">text</div>` → `> text`
   - `<div class="kicker">text</div>` → `@kicker text`
   - `<div class="speaker">Name<span>Role</span></div>` → `@speaker name=Name role=Role`
   - `<p class="subtitle">text</p>` → `@subtitle text`
   - `<p class="tiny">text</p>` → `@tiny text`
   - `<table>...</table>` → markdown pipe tables
3. Convert `px` to `em` (divide by 18) in the `style:` block
4. Remove `section::before` logo CSS — use `logo:` frontmatter field
```

