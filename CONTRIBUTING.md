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

## Setup

```bash
pdm install
pdm run slidr slides.md --pptx
```
