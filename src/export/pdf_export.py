"""DOCX -> PDF via headless LibreOffice.

Verified end-to-end in the build sandbox: LibreOffice Writer (needs
the `libreoffice-writer` package specifically -- `libreoffice-core`
alone has no document filters and fails to even load a .docx) does
correct Devanagari complex-script shaping (conjuncts, matra
reordering) when converting, unlike reportlab-style PDF generation
which has no Indic shaping engine at all. See README for the system
package this needs.

Each call gets its own temp working directory AND its own LibreOffice
user profile (-env:UserInstallation=...). This matters specifically
for a web server: concurrent soffice invocations sharing one profile
directory can lock each other out or corrupt shared state; isolating
per call avoids that at the cost of a slightly slower cold start per
conversion (acceptable for a low-traffic local tool).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .docx_export import render_letter_docx

SOFFICE_TIMEOUT_SECONDS = 90


class PdfExportUnavailable(RuntimeError):
    """Raised when the `soffice` binary or its Writer filters aren't usable."""


class PdfConversionFailed(RuntimeError):
    pass


def _soffice_binary() -> str:
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not binary:
        raise PdfExportUnavailable(
            "soffice/libreoffice not found on PATH. Install libreoffice-writer "
            "(see README) to enable PDF export; DOCX export still works without it."
        )
    return binary


def render_letter_pdf(
    draft_text: str,
    output_path: Path,
    *,
    font_name: str,
    font_size_pt: int,
    margin_cm: float,
    line_spacing: float,
    timeout: int = SOFFICE_TIMEOUT_SECONDS,
) -> Path:
    """Write draft_text into a PDF at output_path, return output_path."""
    binary = _soffice_binary()

    with tempfile.TemporaryDirectory(prefix="letter_export_") as work_dir:
        work_path = Path(work_dir)
        docx_path = work_path / "letter.docx"
        render_letter_docx(
            draft_text, docx_path,
            font_name=font_name, font_size_pt=font_size_pt,
            margin_cm=margin_cm, line_spacing=line_spacing,
        )

        profile_dir = work_path / "lo_profile"
        profile_dir.mkdir()

        result = subprocess.run(
            [
                binary, "--headless", "--norestore",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "pdf",
                "--outdir", str(work_path),
                str(docx_path),
            ],
            capture_output=True, text=True, timeout=timeout,
        )

        produced_pdf = work_path / "letter.pdf"
        if result.returncode != 0 or not produced_pdf.exists():
            raise PdfConversionFailed(
                f"soffice conversion failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(produced_pdf, output_path)

    return output_path
