# CLAUDE.md — Slidr (Python)

Slidr is a Python CLI that turns markdown into styled HTML + PDF + ODP. Uses markdown-it-py for parsing, weasyprint for PDF, odfdo for ODP, Jinja2 for templates. CSS passthrough -- no CSS parser needed. Theme colors extracted via tinycss2 for ODP only.

## Build & test

```bash
pdm install                # install deps
pdm run slidr slides.md    # build HTML
pdm run slidr slides.md --odp     # + ODP
pdm run slidr slides.md --pdf     # + PDF
pdm run pytest             # run tests
```

## Architecture

```
src/slidr/
├── __init__.py
├── __main__.py           # python -m slidr entry
├── cli.py                # Typer CLI (single callback pattern)
├── parser/
│   ├── ast.py            # Node types (Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode, Inline)
│   └── markdown.py       # Main parser: frontmatter → slide split → directives → fenced extraction → markdown-it → token walk
├── plugins/
│   ├── fenced.py         # ::: card / ::: grid extraction (pre-process, not markdown-it plugin)
│   ├── directives.py     # @kicker / @speaker / @subtitle → HTML comment markers → post-process to AttrNode
│   └── cards.py          # Auto-group consecutive Card nodes into Grid
├── theme/
│   ├── parser.py         # tinycss2: parse base.css + theme CSS → PPTX style dict (colors, fonts, padding)
│   └── loader.py         # Raw CSS passthrough + variable extraction (legacy)
├── render/
│   ├── html.py           # Jinja2: Document → HTML. render() + render_presenter()
│   ├── pdf.py            # weasyprint: HTML file → PDF
│   ├── pptx.py           # python-pptx: Document → PPTX. Colors/fonts from theme parser
│   └── templates/
│       ├── shell.html    # Main HTML template (Jinja2)
│       ├── presenter.html # Presenter view (grid: main slide | next preview / notes)
│       ├── base.css      # Structural CSS (reset, layout, screen/print media, nav bar)
│       ├── slidr.js      # Shared JS: navigation, fullscreen, presenter, wheel, keyboard
│       └── presenter.html # Presenter view template
└── themes/
    └── default.css       # Built-in light theme (CSS variables, card, quote, table, tag colors)
```

## Parser pipeline

```
slides.md
  → split_frontmatter (YAML between --- markers)
  → split_slides (\n---\n)
  → per slide: parse_slide
      1. extract_notes (<!-- comment at start)
      2. preprocess_directives (@kicker → <!--attr:kicker:text-->)
      3. extract_fenced (::: card / ::: grid → Card/Grid nodes, content replaced with ◊FENCE_N markers)
      4. markdown_it.parse (gfm-like preset: tables, strikethrough, task lists)
      5. _tokens_to_nodes (heading_open→Heading, paragraph_open→Paragraph, blockquote_open→Quote, table_open→Table, etc.)
      6. interleave_fences (replace ◊FENCE_N markers with actual nodes)
      7. extract_attrs (<!--attr:type:value--> → AttrNode)
      8. group_cards (consecutive Card → Grid auto-wrap)
      9. detect_layout (h1+kicker+speaker→Title, Grid cols→Grid2/3/4, else Content)
```

## Node types

| Type | Source | HTML output |
|------|--------|------------|
| `Heading` | `# Title` / `## Section` | `<h1>` / `<h2>` |
| `Paragraph` | plain text | `<p>` |
| `Grid` | `::: grid {cols=N, class="X"}` | `<div class="grid X" style="grid-template-columns: repeat(N, 1fr)">` |
| `Card` | `::: card {tag="green"}` | `<div class="card tag-green"><h3>...</h3><p>...</p></div>` |
| `Table` | pipe tables | `<table><thead><tbody>` |
| `Quote` | `> text` | `<div class="quote">` |
| `ListNode` | `- item` | `<ul><li>` |
| `AttrNode` | `@kicker text` / `@speaker name=X role=Y` | `<div class="kicker">` / `<div class="speaker">` |
| `Inline::Text` | text | escaped text |
| `Inline::CodeSpan` | `` `code` `` | `<code>` |
| `Inline::SoftBreak` | line break | space |

## Key design decisions

- **Fenced blocks are pre-processed, not markdown-it plugins.** `::: card` and `::: grid` are extracted before markdown parsing, replaced with ◊FENCE_N markers, then re-inserted. This avoids writing a custom markdown-it plugin and handles nesting naturally via recursion.
- **Directives use HTML comment markers.** `@kicker text` becomes `<!--attr:kicker:text-->` which markdown-it treats as an HTML block. Post-processing converts these to AttrNode. This avoids custom inline parsing.
- **CSS is raw passthrough.** The `style:` frontmatter block is injected directly into `<style>`. No CSS parser. The browser (or weasyprint) handles everything. tinycss2 is used ONLY for extracting theme colors for PPTX.
- **Card auto-grouping.** Two or more consecutive `::: card` blocks without a `::: grid` wrapper are automatically wrapped in a Grid with cols=N. This simplifies the markdown syntax.
- **Jinja2 templates.** Both shell.html and presenter.html use Jinja2. CSS injection uses plain text placeholders (SLIDE_W, THEME_CSS, LOGO_CSS) replaced by Python before Jinja2 processes the template, avoiding escaping conflicts.
- **Bidirectional presenter sync.** `window.slidrCurrent` is an `Object.defineProperty` setter that calls `show()`. The presenter polls `window.opener.slidrCurrent` every 300ms. Clicking the presenter's main slide advances both windows.
- **Print CSS in base.css.** `@media print` resets absolute positioning from screen mode. `@page { size: Wpx Hpx; margin: 0 }` sets page dimensions for weasyprint. `page-break-before: always` on sections.
- **Screen scaling via CSS transform.** `body > section` renders at native pixel size (e.g., 1280x720px), then scales to fit viewport via `transform: translate(-50%, -50%) scale(var(--s))` where `--s` is computed by JavaScript.

## Template cascade

```
base.css (structural layout, screen/print rules)
  ↓
default.css (theme: colors, fonts, card/quote/table styling)
  ↓
user style: block (frontmatter overrides)
```

## File conventions

- `base.css` uses `SLIDE_W`, `SLIDE_H`, `THEME_CSS`, `LOGO_CSS` as text placeholders. Python replaces them before Jinja2.
- `shell.html` uses `{% include "slidr.js" %}` for shared JS.
- `presenter.html` has its own inline JS (different from main -- grid layout, sync polling, notes).
- ALL font sizes use `em` (relative to 18pt base on section). No `px` for text.
- Spacing uses `em` for consistency. Percentages converted: `10%` of 720px slide height = 72px / 18 = 4em.

## Testing

- Always add tests after implementing new features. Tests are mandatory, not optional.
- Place tests in `tests/test_<component>.py` where `<component>` matches the module name (e.g. `tests/test_odp.py` for `src/slidr/render/odp.py`, `tests/test_parser.py` for `src/slidr/parser/markdown.py`).
- If a feature spans multiple components, put tests in the file matching the primary component.
- Run `pdm run pytest` after writing tests to confirm they pass.
- Test naming: `test_<function_name>_<scenario>` (e.g. `test_merge_text_elements_separated_by_card`).
