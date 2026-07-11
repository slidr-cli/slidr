# Contributing

## ODP output

Slidr has two ODP output modes:

- **`--odp`**: Programmatic renderer (`src/slidr/render/odp.py`) that builds
  native ODF elements (text frames, tables, lists, images). Pixel-perfect
  layout matching HTML is an ongoing effort. The renderer has full structural
  support but layout positioning is approximate.

- **`--image-odp`**: Screenshot-based renderer that converts each PDF page to
  PNG and embeds them in an ODP file. Always pixel-perfect but no native text
  selection. Uses `pdftoppm` from poppler-utils.

The recommended workflow for editable slides is:

```bash
pdm run slidr slides.md --pdf
# Open in LibreOffice Draw → Select All → Copy → Paste into LibreOffice Impress
```

Areas that need help with the programmatic ODP renderer:

- **Layout fidelity**: Frame positions are estimated from content length.
  Matching HTML/CSS output exactly requires a bounding-box approach (headless
  browser → `getBoundingClientRect()` → ODP frame positions).

- **Font rendering**: ODP uses system fonts. CSS font stacks need mapping
  to single font names.

- **Complex layouts**: Nested grids, two-col layouts with images, and the
  compare layout need more robust positioning.

## Obsidian extension

An Obsidian plugin that renders `.md` files as slidr presentations directly
in the editor. Key features: live preview panel, build-on-save, presenter
mode in a separate pane. Requires familiarity with the Obsidian plugin API
and TypeScript.

## Setup

```bash
pdm install                # core + HTML/PDF/ODP
pdm install -G plot        # + seaborn/matplotlib
pdm run slidr slides.md
```

## seaborn support (done)

` ```seaborn ` fenced blocks execute Python in-process and render as inline SVG.
Requires `pdm install -G plot`. See `src/slidr/render/seaborn.py` and `README.md`.

## graphviz support (done)

` ```dot ` fenced blocks render via the `dot` CLI to SVG. Requires `graphviz`
installed. See `src/slidr/render/dot.py` and `README.md`.

## mermaid support (done)

` ```mermaid ` fenced blocks render via `mmdc` CLI to SVG (HTML) and PDF (ODP).
Requires `mermaid-cli` npm package installed. See `src/slidr/render/ir.py`
mermaid handling and `README.md`.
