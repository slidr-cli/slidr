# Slidr

Markdown to styled PPTX + PDF. Layout primitives (grids, cards, tables) with CSS theming. Single Go binary, no Node runtime.

## Install

```bash
go install github.com/slidr-cli/slidr@latest
```

Or download from releases.

## Quick start

```bash
slidr build slides.md          # → dist/slides.html + dist/slides.pdf
slidr build slides.md --pdf    # PDF only
slidr build slides.md -o out/  # custom output dir
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

::: grid {cols=3}
::: card {tag="green"}
### Topic One
Description here.
:::

::: card {tag="cyan"}
### Topic Two
More description.
:::
:::

> A blockquote with important context.

---

## Data

| Column | Value |
|--------|-------|
| A      | 1     |
| B      | 2     |
```

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

## Fenced blocks

Multi-line blocks using `:::` syntax.

### Grid

```markdown
::: grid {cols=2, class="my-grid"}
...children...
:::
```

Attributes:
- `cols=N` — column count (default: from child count)
- `class="name"` — additional CSS class
- Bare words become CSS classes: `::: grid {cols=4, road-grid}`

### Card

```markdown
::: card {tag="green"}
### Header

Body text. Multiple paragraphs supported.
:::
```

Attributes:
- `tag="green|cyan|yellow|red"` — colored tag badge
- `class="name"` — additional CSS class
- Bare words: `::: card {compact}`

### Nesting

Cards nest inside grids:

```markdown
::: grid {cols=2}
::: card {tag="green"}
### Left
Content.
:::

::: card
### Right
Content.
:::
:::
```

## Tables

Standard markdown pipe tables:

```markdown
| Header | Header |
|--------|--------|
| Cell   | Cell   |
```

## Blockquotes

Standard markdown:

```markdown
> Important quote or callout text.
```

## Images

```markdown
![](path/to/image.png)
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
theme: default       # theme name (loads themes/<name>.css)
title: "..."         # document title
footer: "..."        # slide footer
paginate: true       # show page numbers
size: 16:9           # 16:9 (1280×720), 4:3 (1024×768), 16:10 (1280×800), or "1920x1080"
style: |             # raw CSS injected into output (overrides theme)
  .card { border-color: red; }
```

## Size presets

| Value | Resolution |
|-------|-----------|
| `16:9` (default) | 1280×720 |
| `4:3` | 1024×768 |
| `16:10` | 1280×800 |
| `1920x1080` | custom |

## Styling

CSS is written directly in the `style:` frontmatter block. No CSS parser needed — it's injected raw into the HTML and handled by the browser (for PDF) or mapped to PPTX shapes (future).

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
    border-radius: 0.4em;
  }

  .quote {
    border-left: 0.25em solid var(--accent);
  }
```

Base font-size is 18px on `section`. Use `em` units for spacing to keep proportions consistent.

## Marp migration

1. Remove `marp: true` and `description:` from frontmatter
2. Change `size:` to a supported format (already compatible)
3. Move `style:` block as-is (CSS passthrough)
4. Convert HTML divs to fenced syntax:
   - `<div class="grid">` → `::: grid {cols=3}`
   - `<div class="card">` → `::: card`
   - `<div class="quote">text</div>` → `> text`
   - `<div class="kicker">text</div>` → `@kicker text`
   - `<div class="speaker">Name<span>Role</span></div>` → `@speaker name=Name role=Role`
   - `<p class="subtitle">text</p>` → `@subtitle text`
   - `<p class="tiny">text</p>` → `@tiny text`
   - `<p class="muted">text</p>` → `@muted text`
   - `<table>...</table>` → markdown pipe tables
   - Custom layout divs (tension, scenarios, stack, eco, funnel, maturity) → convert to grid+card blocks
5. Convert `px` values to `em` (base 18px: divide by 18)
6. Remove `section::before` logo CSS — add `![](logo.png)` to the title slide

## Architecture

```
slides.md → parser (goldmark + extractors) → AST
                                               │
                    ┌──────────────────────────┘
                    ▼
          HTML renderer + raw CSS injection
                    │
          ┌────────┴────────┐
          ▼                 ▼
     slides.html       slides.pdf
    (browser nav)    (chromedp)
```

No CSS parser — the browser handles CSS. The Go parser handles markdown structure only.
