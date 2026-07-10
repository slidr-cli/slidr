# Slidr

Markdown to styled HTML slides with PDF and ODP output.

## Install

```bash
pdm install          # core + HTML/PDF/ODP
pdm install -G plot  # + seaborn/matplotlib for inline charts
```

## Usage

```bash
pdm run slidr slides.md              # HTML + presenter view
pdm run slidr slides.md --odp        # + ODP
pdm run slidr slides.md --pdf        # + PDF
pdm run slidr -w slides.md           # watch and rebuild on changes
pdm run slidr --odp -w slides.md     # watch + ODP
```



## Viewer controls

| Action | Key / Mouse |
|--------|-------------|
| Next slide | Left click (on slide area), Right arrow, Down arrow, PgDn, Space |
| Previous slide | Right click, Left arrow, Up arrow, PgUp, Backspace |
| First slide | Home |
| Last slide | End |
| Toggle fullscreen | `f` |
| Open presenter view | Presenter button, `p` |
| Close presenter | `q` |

## Slide directives

```
@kicker text           # title slide eyebrow
@subtitle text         # title slide subtitle
@speaker name=X role=Y # title slide attribution
@layout name           # apply a slide layout
@col                   # explicit column break in two-col / compare layouts
@tiny text             # small annotation
```

## Layouts

| Layout | Usage |
|--------|-------|
| `@layout two-col` | Heading full-width, content split 50/50. Use `@col` for explicit break. |
| `@layout image-right` | Heading full-width, text left, image right |
| `@layout image-left` | Heading full-width, image left, text right |
| `@layout compare` | Two cards side-by-side with an arrow connector, conclusion notes below |
| Custom | `@layout <name>` adds CSS class `layout-<name>`, style via frontmatter `style:` block |

### Compare layout

```markdown
@layout compare

## Before & After

::: card{ tag="red" }
### Without HAMi

GPU utilization at 65%, manual bin-packing required.
:::

::: arrow

:::

::: card{ tag="green" }
### With HAMi

GPU utilization at 92%, zero manual intervention.
:::

::: notes{ tag="green" }
> HAMi is the only CNCF project providing hardware-level GPU sharing.
:::
```

The arrow block accepts text or images:
```
::: arrow
⚠
:::

::: arrow
![](icons/arrow-right.svg)
:::
```

## Fenced blocks

```
::: grid {cols=2}              # responsive grid
::: grid {cols=3}              # 3-column grid
::: card                        # basic card
::: card{ tag="green" }         # colored left border + background
::: card{ tag="quote" }         # accent left border, italic, no fill
::: arrow                       # connector for compare layout
::: notes{ tag="green" }        # full-width conclusion card
> quote text                    # blockquote, renders as .quote div
| col1 | col2 |                 # pipe table
`inline code`                   # inline code
```language                    # fenced code block with syntax highlighting
```mermaid                     # Mermaid diagram, inline SVG
```seaborn                     # Seaborn chart, inline SVG
```d2                          # D2 diagram (legacy, replaced by mermaid)
```

## Layout caveats

`@col` overrides auto-detection in all three layouts (`two-col`,
`image-right`, `image-left`). Use it when auto-split puts content in the
wrong column -- long lists, D2 diagrams, or mixed content types.

## Speaker notes

HTML comments at the top of a slide become speaker notes visible in the presenter view:

```markdown
---

<!--
These are speaker notes.
They appear in the presenter view.
-->
```

## Demo

`examples/features_demo.md` is a 10-slide deck exercising every feature:
title slides, `@layout two-col`, `@layout image-right`, `@layout image-left`,
grids with tagged cards, tables, fenced code blocks with syntax highlighting,
blockquotes, speaker notes, and the `@tiny` / `@kicker` / `@speaker` directives.

```bash
pdm run slidr examples/features_demo.md
```

## Pipeline

```
slides.md
  → markdown-it-py (parse)
  → Document AST (structural: headings, paragraphs, grids, cards, tables)
  → build_ir() (resolve theme styles via tinycss2)
  → SlideIR (per-element: font_size, color, accent + rendered HTML)
     ↙              ↘
  html.py          odp.py
  (_render_elem)   (_render_elem, consumes same IR)
```

The IR is the single source of truth between renderers. Each `Elem` carries
pre-rendered inline HTML (for the browser renderer) plus resolved style
properties like `font_size`, `color`, `accent`, `muted` (for the ODP renderer).
No duplicate node-walking, no diverging implementations of bold/italic/table logic.

## Architecture decisions

### Why Python over Go

Go's ecosystem is thin for presentation tooling. Generating ODP requires a library like odfdo, and Go has nothing comparable. Rendering HTML to PDF needs a real layout engine: weasyprint embeds one in a single Python package; Go would require shelling out to wkhtmltopdf or headless Chrome, both hundreds of megabytes. Markdown parsing has goldmark but its plugin ecosystem is smaller than markdown-it-py. The project iterates heavily on CSS rules, padding math, and layout logic, and Go's compile cycle adds friction to design work where you rebuild after every 2px change.

### Why Python over Rust

Same ecosystem gap, worse compile times. Rust has no odfdo equivalent, no weasyprint equivalent. Pygments for syntax highlighting has syntect in Rust but syntect covers fewer languages. Jinja2 templating maps to Tera which is less mature. Rust's compile time is measured in seconds where Python's is milliseconds, and slide design is inherently iterative.

### Why not Node

Node's dependency footprint is the dealbreaker. A CLI that parses markdown, generates ODP, renders PDF, and templates HTML pulls in 300MB+ of node_modules for marginal functionality. PDF generation requires Puppeteer/Playwright, which bundles a headless Chromium binary (~300MB). Weasyprint is a single Python package that does the same with a fraction of the weight. ODP libraries in Node are less mature than odfdo. Python's stdlib covers path handling, subprocess management, and file I/O without extra packages. The result is a tool you can install and run without downloading half the internet.

### The Python sweet spot

- **odfdo**: ODP generation via OpenDocument XML
- **weasyprint**: HTML/CSS to PDF via embedded layout engine, no browser dependency
- **markdown-it-py**: same parser as the JS ecosystem, GFM support
- **Pygments**: comprehensive syntax highlighting for code blocks
- **Jinja2**: mature templating, CSS injection, template includes
- **Edit-test cycle**: no compile step, instant feedback when tweaking layouts

Deployable as a single binary via PyInstaller or Nuitka when needed.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

## Related projects

- [Marp](https://marp.app/) - Markdown to slides, JS/Electron, extensive ecosystem
- [Slidev](https://sli.dev/) - Markdown to slides, Vue/Node, presenter mode, rich theming
- [reveal.js](https://revealjs.com/) - HTML presentation framework, JS
- [landslide](https://github.com/adamzap/landslide) - Markdown to slides, Python, dormant
- [lookatme](https://github.com/d0c-s4vage/lookatme) - Terminal markdown presentations, Python
