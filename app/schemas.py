"""Pydantic schemas describing API responses and internal records."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Lifecycle status of an uploaded file."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FeatureMeasurement(BaseModel):
    """Measurement result for a single feature."""

    feature_id: int = Field(..., description="Zero-based index of the feature in the dataset.")
    geometry_type: str = Field(..., description="Geometry type, e.g. Polygon, LineString, Point.")
    supported: bool = Field(..., description="Whether a measurement could be computed for this geometry.")
    measurement_type: Optional[str] = Field(
        None, description="'area' for polygons, 'length' for lines, null otherwise."
    )
    value: Optional[float] = Field(
        None, description="Measurement value in the measurement unit (meters-based)."
    )
    unit: Optional[str] = Field(
        None, description="Unit of the value: 'square_meters' or 'meters'."
    )
    note: Optional[str] = Field(
        None, description="Explanation when a geometry is unsupported or partially handled."
    )


class FeatureInfo(BaseModel):
    """Extracted information about a single feature."""

    feature_id: int
    geometry_type: str
    geometry: Optional[dict[str, Any]] = Field(
        None, description="GeoJSON geometry in the file's original CRS."
    )
    properties: dict[str, Any] = Field(default_factory=dict)


class FileInfoResponse(BaseModel):
    """Response for GET /api/files/{id}/."""

    id: str
    filename: str
    status: ProcessingStatus
    feature_count: int
    crs: Optional[str] = Field(None, description="CRS of the source file, e.g. 'EPSG:4326'.")
    source_type: Optional[str] = Field(
        None, description="Detected source format: 'shapefile' or 'kml'."
    )
    error: Optional[str] = Field(None, description="Error detail when status is FAILED.")


class UploadResponse(FileInfoResponse):
    """Response for POST /api/files/ — same shape as file info."""


class MeasurementSummary(BaseModel):
    """Aggregated totals across all measurable features."""

    total_area_sqm: float = 0.0
    total_length_m: float = 0.0
    polygon_count: int = 0
    linestring_count: int = 0
    point_count: int = 0
    unsupported_count: int = 0


class MeasurementsResponse(BaseModel):
    """Response for GET /api/files/{id}/measurements/."""

    id: str
    filename: str
    status: ProcessingStatus
    source_crs: Optional[str] = None
    measurement_crs: Optional[str] = Field(
        None, description="Projected CRS used to compute metric measurements."
    )
    summary: MeasurementSummary
    measurements: list[FeatureMeasurement]
