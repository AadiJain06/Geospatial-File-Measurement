"""In-memory record store for uploaded files and their processing results.

A simple thread-safe dictionary store is used to keep the project dependency
free of a database. The abstraction (`FileStore`) makes it straightforward to
swap in a persistent backend (SQLite, Postgres) later without touching the API
layer.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from app.schemas import (
    FeatureInfo,
    FeatureMeasurement,
    MeasurementSummary,
    ProcessingStatus,
)


@dataclass
class FileRecord:
    """Everything the service knows about one uploaded file."""

    id: str
    filename: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    source_type: Optional[str] = None
    crs: Optional[str] = None
    measurement_crs: Optional[str] = None
    feature_count: int = 0
    features: list[FeatureInfo] = field(default_factory=list)
    measurements: list[FeatureMeasurement] = field(default_factory=list)
    summary: MeasurementSummary = field(default_factory=MeasurementSummary)
    error: Optional[str] = None


class FileStore:
    """Thread-safe in-memory store keyed by file id."""

    def __init__(self) -> None:
        self._records: dict[str, FileRecord] = {}
        self._lock = threading.Lock()

    def create(self, record: FileRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    def get(self, file_id: str) -> Optional[FileRecord]:
        with self._lock:
            return self._records.get(file_id)

    def update(self, record: FileRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    def all(self) -> list[FileRecord]:
        with self._lock:
            return list(self._records.values())


# Singleton store used across the application.
store = FileStore()
