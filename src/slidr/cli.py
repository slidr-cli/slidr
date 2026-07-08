"""slidr CLI entry point."""

from pathlib import Path
from typing import Optional

import typer

from slidr.parser.markdown import parse
from slidr.render.html import render as render_html

app = typer.Typer(help="Markdown to styled PPTX + PDF", no_args_is_help=True)


@app.callback(invoke_without_command=True)
def main(
    file: Path = typer.Argument(None, help="Markdown file to build"),
    output_dir: Optional[Path] = typer.Option(None, "-o", "--output-dir", help="Output directory (default: <input>/dist/)"),
    pdf: bool = typer.Option(False, "--pdf", help="Generate PDF only"),
    pptx: bool = typer.Option(False, "--pptx", help="Generate PPTX only"),
    debug: bool = typer.Option(False, "--debug", help="Dump parsed AST per slide"),
):
    """Build slides from a markdown file. If no file is given, shows help."""
    if file is None:
        raise typer.Exit()

    content = file.read_text()
    doc = parse(content)

    out_dir = output_dir or file.parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = file.stem

    html = render_html(doc, doc.meta.style, doc.meta.logo)
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(html)
    typer.echo(f"Wrote {html_path} ({len(html)} bytes)")

    typer.echo(f"Parsed {len(doc.slides)} slides")
    if debug:
        for i, slide in enumerate(doc.slides):
            typer.echo(f"  Slide {i+1}: {slide.layout.value} ({len(slide.children)} children)")
            for n in slide.children:
                typer.echo(f"    {type(n).__name__}: {_node_summary(n)}")

    if pdf:
        typer.echo("PDF: not yet implemented")
    if pptx:
        typer.echo("PPTX: not yet implemented")


def _node_summary(node) -> str:
    from slidr.parser.ast import Heading, Table, Grid, AttrNode

    if isinstance(node, Heading):
        return f"L{node.level}: {node.content[0].content if node.content else ''}"
    elif isinstance(node, Table):
        return f"({len(node.headers)} cols x {len(node.rows)} rows)"
    elif isinstance(node, Grid):
        return f"cols={node.cols} children={len(node.children)}"
    elif isinstance(node, AttrNode):
        return f"{node.type}: {node.value}"
    return ""
