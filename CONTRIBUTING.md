# Contributing

## PPTX mode

The PPTX renderer (`src/slidr/render/pptx.py`) is structurally complete but needs
work on visual fidelity. What exists: slide creation, heading/paragraph/text/table
placement, grid layout, basic card rendering, theme color extraction, code block
and image fallback rendering.

Areas that need help:

- **Inline formatting**: bold, italic, strikethrough currently extract plain text.
  python-pptx requires per-run formatting via `add_run()` with character-level
  font properties.

- **Speaker notes**: not yet written to PPTX notes slides.

- **Image embedding**: markdown images render as placeholder text. python-pptx
  supports `slide.shapes.add_picture()` for actual image insertion.

- **Layout fidelity**: padding, margins, and font sizes are approximated.
  Matching the HTML/CSS output pixel-for-pixel is the long-term goal.

- **Code block styling**: Pygments-highlighted code blocks render as plain
  monospace text. python-pptx doesn't support rich text in a single run
  natively for syntax-colored output, but multi-run text frames can achieve it.

## Obsidian extension

An Obsidian plugin that renders `.md` files as slidr presentations directly
in the editor. Key features: live preview panel, build-on-save, presenter
mode in a separate pane. Requires familiarity with the Obsidian plugin API
and TypeScript.

## Setup

```bash
pdm install
pdm run slidr slides.md --pptx
```

## matplotlib / seaborn support

Render ````matplotlib` and ````seaborn` fenced code blocks as embedded images
at build time. Requires executing Python in a subprocess, capturing the figure
as base64 PNG, and embedding in the HTML output. Security and dependency
management are the main design questions.
