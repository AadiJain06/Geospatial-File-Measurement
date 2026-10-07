"""Feature extraction and measurement calculation.

Flow
----
1. Normalise the dataset's CRS (default to EPSG:4326 if the source has none).
2. Extract per-feature info (id, geometry type, GeoJSON geometry, properties)
   in the *original* CRS so clients see the data as stored.
3. Choose a projected (metric) CRS via a UTM zone derived from the dataset
   centroid, and reproject a copy for measurement.
4. Compute area for polygonal geometries and length for line geometries.
   Points and any unsupported type are recorded gracefully with a note.
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

import geopandas as gpd

from app.crs import utm_crs_for_lonlat
from app.schemas import FeatureInfo, FeatureMeasurement, MeasurementSummary

# Geometry families we can measure.
_AREA_TYPES = {"Polygon", "MultiPolygon"}
_LENGTH_TYPES = {"LineString", "MultiLineString", "LinearRing"}
_POINT_TYPES = {"Point", "MultiPoint"}

DEFAULT_CRS = "EPSG:4326"


def _clean_properties(row: Any) -> dict[str, Any]:
    """Return JSON-serialisable properties for a feature (geometry dropped)."""
    props: dict[str, Any] = {}
    for key, value in row.items():
        if key == "geometry":
            continue
        if value is None:
            props[key] = None
            continue
        # Convert numpy / pandas scalars and other objects to native types.
        try:
            json.dumps(value)
            props[key] = value
        except (TypeError, ValueError):
            if hasattr(value, "item"):
                try:
                    props[key] = value.item()
                    continue
                except Exception:  # noqa: BLE001
                    pass
            props[key] = str(value)
    return props


def extract_features(gdf: gpd.GeoDataFrame) -> list[FeatureInfo]:
    """Build per-feature info records in the dataset's original CRS."""
    features: list[FeatureInfo] = []
    for idx, (_, row) in enumerate(gdf.iterrows()):
        geom = row.get("geometry")
        geom_type = geom.geom_type if geom is not None else "None"
        geojson_geom: Optional[dict[str, Any]] = None
        if geom is not None and not geom.is_empty:
            try:
                geojson_geom = json.loads(json.dumps(geom.__geo_interface__))
            except Exception:  # noqa: BLE001
                geojson_geom = None
        features.append(
            FeatureInfo(
                feature_id=idx,
                geometry_type=geom_type,
                geometry=geojson_geom,
                properties=_clean_properties(row),
            )
        )
    return features


def _dataset_centroid_lonlat(gdf_wgs84: gpd.GeoDataFrame) -> tuple[float, float]:
    """Return (lon, lat) of the dataset's overall centroid in WGS84."""
    union = gdf_wgs84.geometry.union_all() if hasattr(gdf_wgs84.geometry, "union_all") else gdf_wgs84.geometry.unary_union
    c = union.centroid
    return float(c.x), float(c.y)


def compute_measurements(
    gdf: gpd.GeoDataFrame,
) -> tuple[list[FeatureMeasurement], MeasurementSummary, str, str]:
    """Compute measurements for every feature.

    Returns (measurements, summary, source_crs, measurement_crs).
    """
    # 1. Normalise source CRS.
    if gdf.crs is None:
        gdf = gdf.set_crs(DEFAULT_CRS, allow_override=True)
    source_crs = gdf.crs.to_string() if gdf.crs else DEFAULT_CRS

    # 2. Derive a metric CRS from the centroid (project through WGS84 first).
    gdf_wgs84 = gdf.to_crs(DEFAULT_CRS)
    lon, lat = _dataset_centroid_lonlat(gdf_wgs84)
    metric_crs = utm_crs_for_lonlat(lon, lat)
    measurement_crs = metric_crs.to_string()

    # 3. Reproject for measurement.
    gdf_metric = gdf.to_crs(metric_crs)

    measurements: list[FeatureMeasurement] = []
    summary = MeasurementSummary()

    for idx, geom in enumerate(gdf_metric.geometry):
        if geom is None or geom.is_empty:
            summary.unsupported_count += 1
            measurements.append(
                FeatureMeasurement(
                    feature_id=idx,
                    geometry_type="None",
                    supported=False,
                    note="Empty or missing geometry; no measurement possible.",
                )
            )
            continue

        gtype = geom.geom_type

        if gtype in _AREA_TYPES:
            area = float(geom.area)
            summary.total_area_sqm += area
            summary.polygon_count += 1
            measurements.append(
                FeatureMeasurement(
                    feature_id=idx,
                    geometry_type=gtype,
                    supported=True,
                    measurement_type="area",
                    value=round(area, 4),
                    unit="square_meters",
                )
            )
        elif gtype in _LENGTH_TYPES:
            length = float(geom.length)
            summary.total_length_m += length
            summary.linestring_count += 1
            measurements.append(
                FeatureMeasurement(
                    feature_id=idx,
                    geometry_type=gtype,
                    supported=True,
                    measurement_type="length",
                    value=round(length, 4),
                    unit="meters",
                )
            )
        elif gtype in _POINT_TYPES:
            summary.point_count += 1
            measurements.append(
                FeatureMeasurement(
                    feature_id=idx,
                    geometry_type=gtype,
                    supported=True,
                    measurement_type=None,
                    value=None,
                    unit=None,
                    note="Points have no area or length.",
                )
            )
        else:
            summary.unsupported_count += 1
            measurements.append(
                FeatureMeasurement(
                    feature_id=idx,
                    geometry_type=gtype,
                    supported=False,
                    note=f"Geometry type '{gtype}' is not supported for measurement.",
                )
            )

    summary.total_area_sqm = round(summary.total_area_sqm, 4)
    summary.total_length_m = round(summary.total_length_m, 4)

    if math.isnan(summary.total_area_sqm):
        summary.total_area_sqm = 0.0
    if math.isnan(summary.total_length_m):
        summary.total_length_m = 0.0

    return measurements, summary, source_crs, measurement_crs
