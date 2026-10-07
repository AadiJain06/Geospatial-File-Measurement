"""Orchestration layer: turn an uploaded file into a processed FileRecord."""
from __future__ import annotations

import tempfile

from app.measurement import compute_measurements, extract_features
from app.processing import ProcessingError, parse_file
from app.schemas import ProcessingStatus
from app.store import FileRecord, store


def process_upload(record: FileRecord, saved_path: str) -> FileRecord:
    """Parse, extract features and compute measurements for an upload.

    Updates and persists the record at each stage so its status reflects
    progress. Any failure is captured on the record rather than raised.
    """
    record.status = ProcessingStatus.PROCESSING
    store.update(record)

    try:
        with tempfile.TemporaryDirectory() as workdir:
            parsed = parse_file(saved_path, record.filename, workdir)
            gdf = parsed.gdf

            record.source_type = parsed.source_type
            record.features = extract_features(gdf)
            record.feature_count = len(record.features)

            measurements, summary, source_crs, measurement_crs = compute_measurements(gdf)
            record.measurements = measurements
            record.summary = summary
            record.crs = source_crs
            record.measurement_crs = measurement_crs

            record.status = ProcessingStatus.COMPLETED
    except ProcessingError as exc:
        record.status = ProcessingStatus.FAILED
        record.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - never crash the request
        record.status = ProcessingStatus.FAILED
        record.error = f"Unexpected error during processing: {exc}"

    store.update(record)
    return record
