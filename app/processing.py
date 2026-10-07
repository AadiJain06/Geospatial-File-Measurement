"""Geospatial file processing: parse uploads and extract features.

Supports:
  * Shapefiles delivered as a .zip archive (containing .shp/.shx/.dbf/.prj ...).
  * KML files (.kml).

The parser is intentionally forgiving: it detects the source type, reads the
layer(s) with GeoPandas/Fiona, and returns a single GeoDataFrame plus a
detected source-type label. Errors are surfaced as `ProcessingError` so the
API layer can respond gracefully instead of crashing.
"""
from __future__ import annotations

import glob
import os
import zipfile
from dataclasses import dataclass

import geopandas as gpd
import pandas as pd


class ProcessingError(Exception):
    """Raised when a file cannot be read or contains no usable layer."""


@dataclass
class ParsedData:
    gdf: gpd.GeoDataFrame
    source_type: str  # 'shapefile' | 'kml'


def _read_shapefile_zip(path: str, workdir: str) -> gpd.GeoDataFrame:
    """Extract a zip archive and read the first .shp it contains."""
    extract_dir = os.path.join(workdir, "shp_extract")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(path) as zf:
            # Guard against path traversal in malicious archives.
            for member in zf.namelist():
                target = os.path.realpath(os.path.join(extract_dir, member))
                if not target.startswith(os.path.realpath(extract_dir) + os.sep) and target != os.path.realpath(extract_dir):
                    raise ProcessingError(f"Unsafe path in archive: {member}")
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as exc:
        raise ProcessingError("Uploaded .zip is not a valid zip archive.") from exc

    shp_files = glob.glob(os.path.join(extract_dir, "**", "*.shp"), recursive=True)
    if not shp_files:
        raise ProcessingError("No .shp file found inside the uploaded archive.")

    try:
        gdf = gpd.read_file(shp_files[0])
    except Exception as exc:  # noqa: BLE001 - surface any driver error cleanly
        raise ProcessingError(f"Failed to read shapefile: {exc}") from exc
    return gdf


def _read_kml(path: str) -> gpd.GeoDataFrame:
    """Read a KML file. KML may contain multiple layers; concatenate them."""
    try:
        # Prefer explicit layer enumeration so multi-folder KMLs are fully read.
        import fiona

        layers = fiona.listlayers(path)
    except Exception:  # noqa: BLE001
        layers = []

    frames: list[gpd.GeoDataFrame] = []
    if layers:
        for layer in layers:
            try:
                part = gpd.read_file(path, layer=layer)
                if len(part) > 0:
                    frames.append(part)
            except Exception:  # noqa: BLE001 - skip unreadable layers
                continue

    if not frames:
        # Fallback: single default-layer read.
        try:
            gdf = gpd.read_file(path)
        except Exception as exc:  # noqa: BLE001
            raise ProcessingError(f"Failed to read KML: {exc}") from exc
        return gdf

    combined = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True), crs=frames[0].crs
    )
    return combined


def parse_file(path: str, filename: str, workdir: str) -> ParsedData:
    """Detect the format from the filename and parse it into a GeoDataFrame."""
    lower = filename.lower()

    if lower.endswith(".zip"):
        gdf = _read_shapefile_zip(path, workdir)
        source_type = "shapefile"
    elif lower.endswith(".kml"):
        gdf = _read_kml(path)
        source_type = "kml"
    else:
        raise ProcessingError(
            "Unsupported file type. Upload a .zip containing a shapefile or a .kml file."
        )

    if gdf is None or len(gdf) == 0:
        raise ProcessingError("The file was read but contains no features.")

    if "geometry" not in gdf.columns or gdf.geometry.isna().all():
        raise ProcessingError("The file contains no usable geometries.")

    return ParsedData(gdf=gdf, source_type=source_type)
