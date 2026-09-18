"""FastAPI app: generation UI + admin/data-management UI.

Run with: uvicorn app.main:app --host $WEB_HOST --port $WEB_PORT
(see scripts/run_web.py for a convenience entry point).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import admin, catalog, export, generate

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Hindi Government Letter RAG")

app.include_router(catalog.router)
app.include_router(generate.router)
app.include_router(export.router)
app.include_router(admin.router)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
