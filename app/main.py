"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI

from app.api import router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Upload a geospatial file (zipped Shapefile or KML), extract its "
        "features, and retrieve area/length measurements with correct CRS "
        "handling."
    ),
)

app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    settings.ensure_dirs()


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Root endpoint pointing to the interactive docs."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
