"""API routes for the geospatial measurement service."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import settings
from app.schemas import (
    FeatureInfo,
    FileInfoResponse,
    MeasurementsResponse,
    UploadResponse,
)
from app.service import process_upload
from app.store import FileRecord, store

router = APIRouter(prefix="/api/files", tags=["files"])

_ALLOWED_SUFFIXES = (".zip", ".kml")


def _record_to_file_info(record: FileRecord) -> FileInfoResponse:
    return FileInfoResponse(
        id=record.id,
        filename=record.filename,
        status=record.status,
        feature_count=record.feature_count,
        crs=record.crs,
        source_type=record.source_type,
        error=record.error,
    )


@router.post("/", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Upload and synchronously process a geospatial file.

    Accepts a `.zip` containing a shapefile, or a `.kml` file.
    """
    filename = file.filename or "upload"
    if not filename.lower().endswith(_ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a .zip (shapefile) or .kml file.",
        )

    settings.ensure_dirs()
    file_id = uuid.uuid4().hex[:12]
    saved_path = os.path.join(settings.uploads_dir, f"{file_id}_{os.path.basename(filename)}")

    # Stream to disk while enforcing the size limit.
    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(saved_path, "wb") as out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    out.close()
                    os.remove(saved_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.max_upload_bytes} bytes.",
                    )
                out.write(chunk)
    finally:
        await file.close()

    record = FileRecord(id=file_id, filename=filename)
    store.create(record)

    process_upload(record, saved_path)

    return UploadResponse(**_record_to_file_info(record).model_dump())


@router.get("/{file_id}/", response_model=FileInfoResponse)
async def get_file_info(file_id: str) -> FileInfoResponse:
    """Return metadata and processing status for an uploaded file."""
    record = store.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return _record_to_file_info(record)


@router.get("/{file_id}/features/", response_model=list[FeatureInfo])
async def get_file_features(file_id: str) -> list[FeatureInfo]:
    """Return the extracted features (id, geometry type, geometry, properties)."""
    record = store.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return record.features


@router.get("/{file_id}/measurements/", response_model=MeasurementsResponse)
async def get_file_measurements(file_id: str) -> MeasurementsResponse:
    """Return per-feature measurements and aggregate totals."""
    record = store.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found.")

    return MeasurementsResponse(
        id=record.id,
        filename=record.filename,
        status=record.status,
        source_crs=record.crs,
        measurement_crs=record.measurement_crs,
        summary=record.summary,
        measurements=record.measurements,
    )
