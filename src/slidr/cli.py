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
    pdf: bool = typer.Option(False, "--pdf", help="Generate PDF"),
    odp: bool = typer.Option(False, "--odp", help="Generate ODP (programmatic)"),
    image_odp: bool = typer.Option(False, "--image-odp", help="Generate ODP (PDF screenshots)"),
    watch: bool = typer.Option(False, "-w", "--watch", help="Watch file and rebuild on changes"),
    debug: bool = typer.Option(False, "--debug", help="Dump AST + write debug CSS"),
    css: Optional[Path] = typer.Option(None, "--css", help="Custom CSS theme file (overrides default)"),
):
    if file is None:
        raise typer.Exit()

    if watch:
        _watch(file, output_dir, pdf, odp, image_odp, debug, css)
    else:
        _build(file, output_dir, pdf, odp, image_odp, debug, css)


def _build(file: Path, output_dir: Optional[Path], pdf: bool,
           odp: bool, image_odp: bool, debug: bool, css_path: Optional[Path]) -> None:
    content = file.read_text()
    doc = parse(content)
    dims = doc.meta.dimensions()

    out_dir = output_dir or file.parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    _symlink_assets(file.parent, out_dir, file)
    stem = file.stem

    theme_css = default_theme()
    if css_path and css_path.is_file():
        theme_css += "\n" + css_path.read_text()
    theme_css += "\n" + (doc.meta.style or "")

    html = render_html(doc, theme_css, doc.meta.logo)
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(html)
    typer.echo(f"Wrote {html_path} ({len(html)} bytes)")

    if debug:
        css = base_css().replace("SLIDE_W", str(dims[0])).replace("SLIDE_H", str(dims[1]))
        css = css.replace("THEME_CSS", theme_css)
        css = css.replace("LOGO_CSS", "").replace("{theme_css}", "").replace("{logo_css}", "")
        css_path = out_dir / f"{stem}.css"
        css_path.write_text(css)
        typer.echo(f"Wrote {css_path} (debug CSS, {len(css)} bytes)")

    if odp:
        odp_path = out_dir / f"{stem}.odp"
        render_odp(doc, odp_path, base_css(), theme_css,
                   source_dir=file.parent)
        typer.echo(f"Wrote {odp_path} ({odp_path.stat().st_size} bytes)")
        return

    if image_odp:
        img_path = out_dir / f"{stem}.odp"
        pdf_path = out_dir / f"{stem}.pdf"
        render_pdf(html_path, pdf_path)
        _pdf_to_odp(pdf_path, img_path, dims=dims)
        typer.echo(f"Wrote {img_path} ({img_path.stat().st_size} bytes)")
        return

    if pdf:
        pdf_path = out_dir / f"{stem}.pdf"
        render_pdf(html_path, pdf_path)
        typer.echo(f"Wrote {pdf_path} ({pdf_path.stat().st_size} bytes)")
        return

    typer.echo(f"Parsed {len(doc.slides)} slides")
    if debug:
        for i, slide in enumerate(doc.slides):
            typer.echo(f"  Slide {i+1}: {slide.layout} ({len(slide.children)} children)")
            for n in slide.children:
                typer.echo(f"    {type(n).__name__}: {_node_summary(n)}")


def _watch(file: Path, output_dir: Optional[Path], pdf: bool,
           odp: bool, image_odp: bool, debug: bool, css_path: Optional[Path]) -> None:
    last_mtime = 0
    _build(file, output_dir, pdf, odp, image_odp, debug, css_path)
    typer.echo(f"Watching {file} for changes (Ctrl+C to stop)")

    while True:
        try:
            time.sleep(1)
            mtime = file.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                typer.echo("---")
                _build(file, output_dir, pdf, odp, image_odp, debug, css_path)
        except KeyboardInterrupt:
            typer.echo("\nStopped watching.")
            break
        except Exception as e:
            typer.echo(f"Error: {e}")


def _pdf_to_odp(pdf_path: Path, output_path: Path, dims: tuple[int, int]) -> None:
    import os, subprocess, tempfile
    from odfdo import Document, DrawPage, Frame

    sw, sh = dims
    odp = Document("presentation")
    odp.body.clear()

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", str(pdf_path), f"{tmp}/page"],
            capture_output=True, text=True, timeout=60,
        )
        for png_file in sorted(Path(tmp).glob("page-*.png")):
            i = int(png_file.stem.split("-")[1]) - 1
            page = DrawPage(f"slide{i + 1}", name=f"Slide {i + 1}")
            uri = odp.add_file(str(png_file))
            frame = Frame.image_frame(
                image=uri, text="",
                size=(f"{sw * 2.54 / 96:.2f}cm", f"{sh * 2.54 / 96:.2f}cm"),
                position=("0cm", "0cm"),
                anchor_type="page",
            )
            page.append(frame)
            odp.body.append(page)

    odp.save(str(output_path), pretty=True)


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
    for item in source_dir.iterdir():
        if item.name == dist_dir.name or item == input_file:
            continue
        dest = dist_dir / item.name
        if not dest.exists():
            dest.symlink_to(item.resolve())
