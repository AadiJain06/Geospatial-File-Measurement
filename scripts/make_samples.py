"""Generate sample files for manual testing.

Creates (under ./samples):
  * sample.kml         - a KML with a polygon, a line, and a point (EPSG:4326)
  * sample_shp.zip     - a zipped polygon shapefile (EPSG:4326)

Note: the ESRI Shapefile format allows only one geometry type per file, so
the shapefile sample contains polygons only. KML can mix geometry types, so
the KML sample exercises polygon + line + point in a single file.

Run: python scripts/make_samples.py
"""
from __future__ import annotations

import os
import zipfile

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

OUT_DIR = "samples"


def build_gdf() -> gpd.GeoDataFrame:
    # A roughly 3-block area in central Bengaluru (EPSG:4326).
    polygon = Polygon(
        [
            (77.5900, 12.9700),
            (77.5920, 12.9700),
            (77.5920, 12.9720),
            (77.5900, 12.9720),
            (77.5900, 12.9700),
        ]
    )
    line = LineString([(77.5900, 12.9700), (77.5950, 12.9750)])
    point = Point(77.5910, 12.9710)

    return gpd.GeoDataFrame(
        {
            "name": ["block", "road", "marker"],
            "category": ["parcel", "line", "poi"],
        },
        geometry=[polygon, line, point],
        crs="EPSG:4326",
    )


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    gdf = build_gdf()

    # KML
    kml_path = os.path.join(OUT_DIR, "sample.kml")
    gdf.to_file(kml_path, driver="KML")
    print(f"wrote {kml_path}")

    # Shapefile -> zip (polygons only; shapefiles are single-geometry-type).
    polygons = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    shp_dir = os.path.join(OUT_DIR, "_shp")
    os.makedirs(shp_dir, exist_ok=True)
    shp_path = os.path.join(shp_dir, "sample.shp")
    polygons.to_file(shp_path, driver="ESRI Shapefile")

    zip_path = os.path.join(OUT_DIR, "sample_shp.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(shp_dir):
            zf.write(os.path.join(shp_dir, fname), arcname=fname)
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
