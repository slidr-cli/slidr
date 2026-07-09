"""PDF renderer using weasyprint."""

from pathlib import Path
from weasyprint import HTML


def render(html_path: Path, output_path: Path) -> None:
    """Render an HTML file to PDF."""
    HTML(filename=str(html_path)).write_pdf(target=str(output_path))
