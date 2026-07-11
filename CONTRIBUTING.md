# Contributing

## ODP output

Slidr has two ODP output modes. Neither is complete, but the screenshot
approach is production-ready.

- **`--image-odp` (production-ready)**: Renders each slide to PNG via weasyprint +
  pdftoppm, embeds in an ODP file. Always pixel-perfect. No native text selection
  or editing, but perfect for LibreOffice Draw → Impress copy-paste workflow.

- **`--odp` (work in progress)**: Programmatic renderer that builds native ODF
  elements. Renders structurally but layout positioning doesn't match HTML yet.

The recommended workflow for editable slides:

```bash
pdm run slidr slides.md --pdf
# Open in LibreOffice Draw → Select All → Copy → Paste into LibreOffice Impress
```

Areas that need help with the programmatic ODP renderer:

- **Layout fidelity**: Frame positions estimated from content length
- **Headless bounding-box**: Render in Chrome, extract exact positions via JS
- **Font rendering**: ODP uses system fonts, CSS font stacks need mapping
- **Complex layouts**: Nested grids, two-col with images, compare layout

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

` ```mermaid ` fenced blocks render via the `mmdc` Python package to SVG (HTML)
and PDF (ODP). The `mmdc` package is bundled as a dependency. See
`src/slidr/render/ir.py` mermaid handling and `README.md`.
