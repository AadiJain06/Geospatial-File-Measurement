"""CRS selection utilities.

Measurements (area, length) must not be computed in geographic coordinates
(degrees of latitude/longitude). We therefore reproject geometries into a
projected CRS whose units are meters before measuring.

Strategy
--------
We pick a UTM (Universal Transverse Mercator) zone derived from the dataset's
centroid. UTM minimises distortion locally and keeps results in meters, which
is accurate for the typical extent of surveyed files. For datasets that span
very large areas a single UTM zone is a compromise, but it is a sensible,
widely-used default and avoids hard-coding a single global projection.
"""
from __future__ import annotations

from pyproj import CRS


def utm_crs_for_lonlat(lon: float, lat: float) -> CRS:
    """Return the UTM CRS whose zone contains the given lon/lat point.

    Northern hemisphere zones use EPSG:326xx, southern use EPSG:327xx.
    """
    zone = int((lon + 180.0) / 6.0) + 1
    zone = min(max(zone, 1), 60)
    if lat >= 0:
        epsg = 32600 + zone
    else:
        epsg = 32700 + zone
    return CRS.from_epsg(epsg)
