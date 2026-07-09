# Slidr

Markdown to styled PPTX + PDF. Cards, grids, tables, directives. CSS theming with cascading overrides. Python + markdown-it + weasyprint.

## Why

**Marp and Slidev are too heavy.** Marp-core is a JavaScript framework that wraps every slide in SVG foreignObjects and requires a full Node.js toolchain. Slidev is a Vue SPA with 55,000+ lines of TypeScript -- it's a web application, not a presentation tool. Both force you to write raw HTML divs for anything beyond basic headings and paragraphs. Want a card grid? Write `<div class="grid"><div class="card">...`. Want a kicker above your title? More divs. The markdown becomes half HTML.

**Rust and Go weren't the answer.** We tried pulldown-cmark (Rust) and goldmark (Go). The table extension silently failed in pulldown-cmark 0.13. comrak's arena allocator created lifetime headaches. The fundamental problem: neither ecosystem made custom block syntax simple -- pulldown-cmark has an extension API but it is more complex than markdown-it-py. Adding `::: card` / `::: grid` support required pre-processing hacks or forking the parser.

**Python's ecosystem fits.** markdown-it-py handles GFM tables natively (no silent failures). Its token-based API makes it easy to walk the AST and convert to our own node types. weasyprint renders HTML+CSS to PDF without Chrome. python-pptx produces native PowerPoint shapes. Jinja2 templates are cleaner than Go's text/template or Rust's tera.

**What slidr does differently.** You write markdown with semantic annotations -- not HTML div soup. Cards are `::: card`, grids auto-form from consecutive cards, directives are `@kicker text`. The CSS handles theming. The parser handles structure. No writing `<div class="...">` for every layout element.

## Install

```bash
pdm install
```

## Quick start

```bash
pdm run slidr slides.md           # → dist/slides.html + dist/slides.presenter.html
pdm run slidr slides.md --pdf     # → dist/slides.pdf
pdm run slidr slides.md --pptx    # → dist/slides.pptx
pdm run slidr slides.md --debug   # dump parsed AST
```

Output goes to `<input_dir>/dist/` by default.

## Slide structure

Slides are separated by `---`. Frontmatter is YAML between `---` markers.

```markdown
---
title: My Presentation
footer: "Conf 2026"
size: 16:9
paginate: true
logo: ./assets/logo.png
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

> A blockquote with context.

---

## Data

| Column | Value |
|--------|-------|
| A      | 1     |
```

## Markdown extensions

### Cards

Cards are the primary content container. Each card has a heading and body text.

```markdown
::: card
### Header
Body text. Supports multiple paragraphs.
:::
```

**Attributes** (any `key=value` becomes a `key-value` CSS class):

```markdown
::: card {tag="green"}
### Header
Body
:::
```
→ `<div class="card tag-green">`

**Auto-grouping**: two or more consecutive cards automatically form a grid. Column count matches the number of cards.

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
→ 2-column grid. No `::: grid` wrapper needed.

### Grids

Explicit grids for custom column counts or CSS classes.

```markdown
::: grid {cols=4, class="road-grid"}
::: card
### Card 1
:::
::: card
### Card 2
:::
:::
```

**Attributes:**

| Key | Description |
|-----|-------------|
| `cols=N` | Column count (default: auto from cards) |
| `class="name"` | CSS class |
| Bare words | Shorthand: `::: grid {road-grid}` |

### Directives

Single-line annotations using `@type` syntax.

| Directive | Output |
|-----------|--------|
| `@kicker text` | `<div class="kicker">text</div>` |
| `@subtitle text` | `<p class="subtitle">text</p>` |
| `@speaker name=Name role=Role` | `<div class="speaker">Name \| Role</div>` |
| `@tiny text` | `<p class="tiny">text</p>` |
| `@muted text` | `<p class="muted">text</p>` |

Custom types work generically: `@custom-badge text` → `<p class="custom-badge">text</p>`.

### Tables

Standard GFM pipe tables with markdown-it.

```markdown
| Header | Header |
|--------|--------|
| Cell   | Cell   |
```

### Blockquotes

```markdown
> Callout or quoted text.
Rendered as `<div class="quote">`.
```

### Speaker notes

HTML comments at the start of a slide become speaker notes (visible in presenter view).

```markdown
---

<!--
These are speaker notes.
Visible in presenter mode.
-->

## Slide Title
```

## Frontmatter

```yaml
title: "..."         # document title
footer: "..."        # slide footer text
paginate: true       # show page numbers
size: 16:9           # 16:9 → 1280x720, 4:3 → 1024x768, or "1920x1080"
logo: ./assets/logo.png  # logo on every slide
style: |             # raw CSS injected into output (overrides defaults)
  :root { --accent: #0fd05d; }
```

## Styling

CSS is written in the `style:` frontmatter block. Injected raw into the HTML output.

**Cascade order**: base.css (layout) → default theme → user `style:` block.

**Base font**: 18pt on `section`. Internal spacing uses `em` for consistency.

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
```

## Viewer features

- **Arrow keys**: navigate slides
- **Mouse wheel**: scroll through slides
- **f**: toggle fullscreen
- **q**: close presenter window
- **▶ button**: open presenter view (current slide + next preview + speaker notes)
- **Bidirectional sync**: navigating in either window updates the other

## Output formats

| Format | Engine | Notes |
|--------|--------|-------|
| HTML | Jinja2 | Screen + print CSS, presenter view |
| PDF | weasyprint | Pure Python, no Chrome dependency |
| PPTX | python-pptx | Native shapes, theme colors from CSS via tinycss2 |

## Marp migration

- Remove `marp: true` from frontmatter
- `<div class="grid">` → remove wrapper (cards auto-group)
- `<div class="card"><h3>...</h3><p>...</p></div>` → `::: card` / `### ...` / body
- `<div class="quote">text</div>` → `> text`
- `<div class="kicker">text</div>` → `@kicker text`
- `<div class="speaker">Name<span>Role</span></div>` → `@speaker name=Name role=Role`
- `<table>` → markdown pipe table
- `px` → `em` (divide by 18) in CSS
- `section::before` logo → `logo:` frontmatter field

## Related projects

- [Marp](https://marp.app) -- Markdown Presentation Ecosystem (Node.js)
- [Slidev](https://sli.dev) -- Presentation Slides for Developers (Vue/TypeScript)

Both inspired slidr. If slidr doesn't fit your workflow, try them.

## License

MIT
