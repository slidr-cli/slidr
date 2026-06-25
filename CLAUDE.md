# CLAUDE.md — Slidr

Slidr is a Go CLI that turns markdown into styled PPTX + PDF. Think Marp but with semantic layout primitives instead of raw CSS div soup.

## Build & test

```bash
go build .                # binary: ./slidr
go test ./... -count=1    # run all tests
go vet ./...              # static analysis
```

## Architecture

```
internal/
├── parser/
│   ├── ast.go        # Node types (Grid, Card, Table, Quote, AttrNode, etc.)
│   ├── parser.go     # Goldmark pipeline + fenced divs + directives + HTML extraction
│   └── parser_test.go
├── theme/
│   └── loader.go     # Raw CSS passthrough (no parsing needed)
└── render/
    ├── html/
    │   ├── render.go     # AST → HTML (inline rendering, no template for nodes)
    │   └── templates/
    │       └── shell.tmpl  # Page skeleton, @page, nav bar, screen/print CSS
    ├── pdf/
    │   └── pdf.go      # chromedp: HTML → PDF via headless Chrome
    └── pptx/           # (not yet implemented)
```

## Parser pipeline

```
slides.md
  → splitSlides (--- separators)
  → per slide: parseSlideContent
      1. extractFencedNodes  (::: card, ::: grid → AST nodes, removed from content)
      2. extractDirectives   (@kicker, @speaker, etc. → AttrNodes, removed)
      3. goldmark.Parse      (remaining markdown → headings, paragraphs, blockquotes, lists, tables)
      4. Merge: goldmark nodes first (headings/quotes), then fenced (grids/cards), then directives
```

## Node types

| Type | Source | HTML output |
|------|--------|------------|
| `Grid` | `::: grid {cols=N}` | `<div class="grid" style="grid-template-columns:...">` |
| `Card` | `::: card {tag="green"}` | `<div class="card"><h3>...</h3><p>...</p></div>` |
| `Table` | markdown pipe or HTML `<table>` | `<table>...</table>` |
| `Quote` | `> text` | `<div class="quote">text</div>` |
| `AttrNode` | `@type value` | `<div class="type">` or type-specific HTML |
| `Heading` | `# Title` / `## Section` | `<h1>` / `<h2>` |
| `Paragraph` | plain text | `<p>` |
| `ListNode` | `- item` | `<ul><li>` |
| `Kicker` | `@kicker` (maps to AttrNode) | `<div class="kicker">` |
| `Speaker` | `@speaker` (maps to AttrNode) | `<div class="speaker"><span>` |
| `ImageNode` | `![](url)` | `<img>` |

## Style brief

- **Base font-size**: 18px on `section`. All spacing in `em` units.
- **CSS passthrough**: The `style:` frontmatter block goes directly into `<style>` — no parser, no processing. The browser handles everything.
- **Cascade order**: Reset → layout defaults → theme CSS → screen/print rules. Theme overrides defaults.
- **Screen mode**: One slide visible at a time. Nav bar with prev/next. Arrow key navigation. Aspect ratio preserved with `calc()` scaling.
- **Print/PDF mode**: All slides paginated. `@page { margin: 0 }`, `page-break-after: always`. chromedp sets paper size from slide dimensions.
- **Layout defaults** (in shell.tmpl, before theme CSS):
  ```css
  section { font-size: 18px; }
  .grid { display: grid; gap: 1em; }
  .card { border-radius: 0.4em; padding: 1em; }
  .card h3 { margin-bottom: 0.5em; }
  .card p { margin-bottom: 0.5em; }
  .quote { border-left: 0.25em solid; padding-left: 1em; }
  p { margin-bottom: 0.5em; }
  h2, h3 { margin-bottom: 0.5em; }
  ```

## Converting from Marp

### Automated (Python)

The conversion from Marp HTML divs to slidr fenced syntax is a multi-step process:

1. **Tables**: Convert `<table>...</table>` to markdown pipe tables
2. **Quotes**: `<div class="quote">text</div>` → `> text`
3. **Directives**: Convert single-line wrappers:
   - `<div class="kicker">text</div>` → `@kicker text`
   - `<p class="subtitle">text</p>` → `@subtitle text`
   - `<div class="speaker">Name<span>Role</span></div>` → `@speaker name=Name role=Role`
   - `<p class="tiny">text</p>` → `@tiny text`
   - `<p class="muted">text</p>` → `@muted text`
4. **Grids and cards**: Convert nested `<div class="grid">` / `<div class="card">` to fenced syntax. Track div nesting depth to find matching close tags (regex `.*?</div>` fails on nested divs).
5. **Custom layouts**: Unwrap custom div classes (tension, scenarios, stack, eco, funnel, maturity, road-grid, compact-grid, evidence-grid, end-grid) into grid+card blocks or simple text.
6. **CSS units**: Convert `px` to `em` (divide by 18 for the base font-size). Run on the frontmatter `style:` block only.
7. **Cleanup**: Strip inline `style=""` attributes from body. Remove remaining HTML fragments. De-indent to prevent goldmark code block artifacts.

### Manual checks after conversion

- Verify `::: grid {cols=N}` blocks have the correct `class=` attribute matching original (mt-grid, evidence-grid, end-grid, road-grid, compact-grid, end-links)
- Cards that need border colors: `::: card {border-green}`, `::: card {border-red}`
- Custom diagram slides (stack, funnel, eco pyramid) may need manual restructuring
- Images: add `![](path)` to slides that had embedded images
- Logo: remove `section::before` CSS, add `![](logo.png)` to title slide
- Font sizes: verify em conversions at 18px base (56px → 3.11em, 38px → 2.11em, 22px → 1.22em)

## Resolution

- `size: 16:9` → 1280×720 (matching Marp's internal canvas)
- `size: 4:3` → 1024×768
- `size: 16:10` → 1280×800
- `size: 1920x1080` → custom explicit dimensions
- Values outside [320, 7680] are clamped. Input over 32 chars is rejected.

## Key decisions

- **No CSS parser**: The browser handles CSS. We only parse markdown structure.
- **No goldmark extension for fenced divs**: Instead, we pre-process fenced divs into AST nodes before goldmark runs. This is simpler than writing a goldmark BlockParser.
- **Source order preservation**: Goldmark nodes (headings, blockquotes) come before fenced nodes (grids, cards) in output order. This matches the common markdown pattern where content precedes structural blocks.
- **Generic directives**: `@type value` parses any type name (`[\w-]+`). Unknown types render as `<div class="type">`. No code changes needed to add new directive types.
