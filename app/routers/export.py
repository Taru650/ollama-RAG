"""POST /api/export/docx and /api/export/pdf -- download the generated draft."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.schemas import ExportRequest
from config.settings import settings
from src.export.docx_export import render_letter_docx
from src.export.pdf_export import PdfConversionFailed, PdfExportUnavailable, render_letter_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


def _cleanup(path: Path) -> None:
    path.unlink(missing_ok=True)


@router.post("/docx")
def export_docx(body: ExportRequest) -> FileResponse:
    settings.export_tmp_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.export_tmp_dir / f"letter_{uuid.uuid4().hex}.docx"
    render_letter_docx(
        body.draft, output_path,
        font_name=settings.docx_font_name,
        font_size_pt=settings.docx_font_size_pt,
        margin_cm=settings.docx_margin_cm,
        line_spacing=settings.docx_line_spacing,
    )
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="letter.docx",
        background=BackgroundTask(_cleanup, output_path),
    )


@router.post("/pdf")
def export_pdf(body: ExportRequest) -> FileResponse:
    settings.export_tmp_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.export_tmp_dir / f"letter_{uuid.uuid4().hex}.pdf"
    try:
        render_letter_pdf(
            body.draft, output_path,
            font_name=settings.docx_font_name,
            font_size_pt=settings.docx_font_size_pt,
            margin_cm=settings.docx_margin_cm,
            line_spacing=settings.docx_line_spacing,
        )
    except PdfExportUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PdfConversionFailed as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename="letter.pdf",
        background=BackgroundTask(_cleanup, output_path),
    )
