"""PDF renderer using weasyprint."""

from pathlib import Path
from weasyprint import HTML


def render(html_path: Path, output_path: Path, optimize_images: bool = False) -> None:
    if optimize_images:
        HTML(filename=str(html_path)).write_pdf(
            target=str(output_path),
            jpeg_quality=85,
            optimize_images=True,
            dpi=200,
        )
    else:
        HTML(filename=str(html_path)).write_pdf(target=str(output_path))
