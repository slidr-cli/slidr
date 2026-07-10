"""slidr CLI entry point."""

import time
from pathlib import Path
from typing import Optional

import typer

from slidr.parser.markdown import parse
from slidr.render.html import render as render_html, default_theme, base_css
from slidr.render.odp import render as render_odp
from slidr.render.pdf import render as render_pdf

app = typer.Typer(help="Markdown to styled HTML + ODP + PDF", no_args_is_help=True)


@app.callback(invoke_without_command=True)
def main(
    file: Path = typer.Argument(None, help="Markdown file to build"),
    output_dir: Optional[Path] = typer.Option(None, "-o", "--output-dir", help="Output directory (default: <input>/dist/)"),
    pdf: bool = typer.Option(False, "--pdf", help="Generate PDF only"),
    odp: bool = typer.Option(False, "--odp", help="Generate ODP"),
    watch: bool = typer.Option(False, "-w", "--watch", help="Watch file and rebuild on changes"),
    debug: bool = typer.Option(False, "--debug", help="Dump parsed AST per slide"),
):
    """Build slides from a markdown file. If no file is given, shows help."""
    if file is None:
        raise typer.Exit()

    if watch:
        _watch_and_build(file, output_dir, pdf, odp, debug)
    else:
        _build(file, output_dir, pdf, odp, debug)


def _build(file: Path, output_dir: Optional[Path], pdf: bool,
           odp: bool, debug: bool) -> None:
    content = file.read_text()
    doc = parse(content)

    out_dir = output_dir or file.parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    _symlink_assets(file.parent, out_dir, file)
    stem = file.stem

    html = render_html(doc, default_theme() + "\n" + (doc.meta.style or ""), doc.meta.logo)
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(html)
    typer.echo(f"Wrote {html_path} ({len(html)} bytes)")

    if odp:
        odp_path = out_dir / f"{stem}.odp"
        render_odp(doc, odp_path, base_css(), default_theme() + "\n" + (doc.meta.style or ""),
                   source_dir=file.parent)
        typer.echo(f"Wrote {odp_path} ({odp_path.stat().st_size} bytes)")
        return

    if pdf:
        pdf_path = out_dir / f"{stem}.pdf"
        render_pdf(html_path, pdf_path)
        typer.echo(f"Wrote {pdf_path} ({pdf_path.stat().st_size} bytes)")
        return

    typer.echo(f"Parsed {len(doc.slides)} slides")
    if debug:
        for i, slide in enumerate(doc.slides):
            typer.echo(f"  Slide {i+1}: {slide.layout.value} ({len(slide.children)} children)")
            for n in slide.children:
                typer.echo(f"    {type(n).__name__}: {_node_summary(n)}")


def _watch_and_build(file: Path, output_dir: Optional[Path], pdf: bool,
                     odp: bool, debug: bool) -> None:
    """Watch a markdown file and rebuild on changes."""
    last_mtime = 0

    _build(file, output_dir, pdf, odp, debug)
    typer.echo(f"Watching {file} for changes (Ctrl+C to stop)")

    while True:
        try:
            time.sleep(1)
            current_mtime = file.stat().st_mtime
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                typer.echo("---")
                _build(file, output_dir, pdf, odp, debug)
        except KeyboardInterrupt:
            typer.echo("\nStopped watching.")
            break
        except Exception as e:
            typer.echo(f"Error: {e}")


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


def _symlink_assets(source_dir: Path, dist_dir: Path, input_file: Path) -> None:
    """Symlink everything except the input .md and dist itself into dist."""
    for item in source_dir.iterdir():
        if item.name == dist_dir.name or item == input_file:
            continue
        dest = dist_dir / item.name
        if not dest.exists():
            dest.symlink_to(item.resolve())
