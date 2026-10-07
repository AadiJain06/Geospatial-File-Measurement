# Geospatial File Measurement API

A backend service built with **FastAPI** that accepts a geospatial file
(a zipped Shapefile or a KML), extracts its features, handles coordinate
reference systems correctly, and returns measurement information — **area**
for polygons and **length** for lines.

---

## Features

- Upload a `.zip` containing a Shapefile or a `.kml` file.
- Extract every feature with its **ID/index**, **geometry type**, **geometry**
  (GeoJSON), **CRS**, and **properties/attributes**.
- Calculate **area** (polygons) and **length** (lines) in meters.
- **Correct CRS handling**: geometries in geographic coordinates (e.g.
  `EPSG:4326`) are reprojected to a projected, metric CRS before measuring —
  area and distance are never computed from raw degrees.
- Graceful handling of unsupported geometry types (no crashes).
- Interactive API docs via Swagger UI at `/docs`.

---

## Setup

### Prerequisites

- Python 3.10+
- The geospatial stack (GeoPandas, Shapely, pyproj, Fiona) relies on GEOS,
  PROJ, and GDAL. On most platforms `pip install` of the pinned wheels pulls
  these in automatically. If you hit build issues, Conda is a reliable
  alternative: `conda install -c conda-forge geopandas`.

### Install and run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn app.main:app --reload
```

The API is now available at `http://127.0.0.1:8000`.
Interactive docs: `http://127.0.0.1:8000/docs`.

### Generate sample files (optional)

```bash
python scripts/make_samples.py
# creates samples/sample.kml and samples/sample_shp.zip
```

---

## API

Base path: `/api/files`

### 1. Upload a file

`POST /api/files/`

Form-data body with a single `file` field.

```bash
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@samples/sample.kml"
```

**Response** `201 Created`

```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "sample.kml",
  "status": "COMPLETED",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "source_type": "kml",
  "error": null
}
```

On failure the record is still created with `status: "FAILED"` and an `error`
message describing what went wrong.

### 2. File information

`GET /api/files/{id}/`

```bash
curl http://127.0.0.1:8000/api/files/a1b2c3d4e5f6/
```

**Response** `200 OK`

```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "sample.kml",
  "status": "COMPLETED",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "source_type": "kml",
  "error": null
}
```

### 3. Measurements

`GET /api/files/{id}/measurements/`

```bash
curl http://127.0.0.1:8000/api/files/a1b2c3d4e5f6/measurements/
```

**Response** `200 OK`

```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "sample.kml",
  "status": "COMPLETED",
  "source_crs": "EPSG:4326",
  "measurement_crs": "EPSG:32643",
  "summary": {
    "total_area_sqm": 47568.21,
    "total_length_m": 785.4,
    "polygon_count": 1,
    "linestring_count": 1,
    "point_count": 1,
    "unsupported_count": 0
  },
  "measurements": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "supported": true,
      "measurement_type": "area",
      "value": 47568.21,
      "unit": "square_meters",
      "note": null
    },
    {
      "feature_id": 1,
      "geometry_type": "LineString",
      "supported": true,
      "measurement_type": "length",
      "value": 785.4,
      "unit": "meters",
      "note": null
    },
    {
      "feature_id": 2,
      "geometry_type": "Point",
      "supported": true,
      "measurement_type": null,
      "value": null,
      "unit": null,
      "note": "Points have no area or length."
    }
  ]
}
```

### 4. Features (bonus)

`GET /api/files/{id}/features/`

Returns the extracted features — `feature_id`, `geometry_type`, `geometry`
(GeoJSON in the source CRS) and `properties`.

### Health

`GET /health` → `{ "status": "ok" }`

---

## Architecture

### Application structure

```
app/
  main.py         # FastAPI app + meta routes (/, /health)
  api.py          # /api/files routes (upload, info, features, measurements)
  service.py      # Orchestration: upload -> parse -> extract -> measure
  processing.py   # Read Shapefile (.zip) / KML into a GeoDataFrame
  measurement.py  # Feature extraction + area/length computation
  crs.py          # Projected-CRS selection (UTM from centroid)
  store.py        # Thread-safe in-memory record store
  schemas.py      # Pydantic request/response models
  config.py       # Settings (storage dir, upload size limit)
scripts/
  make_samples.py # Generate sample KML + zipped shapefile
```

The layers are deliberately separated so each concern can be tested and
replaced independently (e.g. swap the in-memory store for a database).

### File-processing flow

1. **Upload** (`api.py`) — validate the extension (`.zip` / `.kml`), stream the
   file to `storage/uploads/` while enforcing a size limit, and create a
   `FileRecord` with status `PENDING`.
2. **Parse** (`processing.py`) — detect the format:
   - `.zip`: safely extract (with a zip-slip guard) and read the first `.shp`.
   - `.kml`: enumerate layers and read/concatenate them.
   Everything becomes a single GeoPandas `GeoDataFrame`.
3. **Extract** (`measurement.py`) — build per-feature records: index, geometry
   type, GeoJSON geometry (in the original CRS), and JSON-safe properties.
4. **Measure** — compute area/length (see below).
5. **Persist** — the `FileRecord` status moves `PROCESSING → COMPLETED`
   (or `FAILED` with an error message). Processing never raises out of the
   request; failures are captured on the record.

### Measurement calculation flow

- **Polygon / MultiPolygon** → `area`, in `square_meters`.
- **LineString / MultiLineString** → `length`, in `meters`.
- **Point / MultiPoint** → no measurement (recorded with a note).
- **Any other / empty geometry** → marked `supported: false` with an
  explanatory note; it is counted in `unsupported_count` but never crashes the
  request.
- An aggregate `summary` reports totals and per-type counts.

### CRS handling

Area and length must not be computed in degrees. The flow is:

1. Normalise the source CRS — if the file declares none, default to
   `EPSG:4326`. The original CRS is reported back as `source_crs`.
2. Reproject a copy of the data to WGS84 and take the dataset **centroid**.
3. Select the **UTM zone** containing that centroid
   (`EPSG:326xx` north / `EPSG:327xx` south) — a metric projection with low
   local distortion. This is reported as `measurement_crs`.
4. Reproject the geometries into that CRS and compute area/length in meters.

Extracted geometries in the `features` endpoint are returned in the **original**
CRS so clients see the data exactly as stored, while measurements are always
metric.

---

## Design Decisions

- **FastAPI over Django + DRF.** The service is small and I/O-light; FastAPI
  gives concise code, automatic OpenAPI docs, and Pydantic validation with
  minimal boilerplate. DRF would add project scaffolding without a clear
  benefit here.
- **GeoPandas / Fiona / Shapely / pyproj.** The de-facto Python geospatial
  stack. Fiona reads both Shapefile and KML drivers, GeoPandas provides a
  uniform `GeoDataFrame`, and pyproj handles reprojection — avoiding
  hand-rolled geometry/CRS code.
- **UTM-from-centroid for the projected CRS.** A simple, well-understood
  default that keeps measurements in meters with low local distortion.
  _Alternatives considered:_ a single world projection like Web Mercator
  (`EPSG:3857`) — rejected because its area distortion is large away from the
  equator; or an equal-area projection like World Mollweide for areas — a good
  option for global datasets, but UTM is more accurate for the local extents
  typical of surveyed files. For datasets spanning many UTM zones a single zone
  is a compromise (see Future Scope).
- **Synchronous processing.** Files are processed within the upload request so
  the response already reflects `COMPLETED`/`FAILED`. The status field and the
  background-friendly `FileRecord` design leave room to move to async/queued
  processing later.
- **In-memory store.** Keeps the project dependency-free and easy to run. The
  `FileStore` abstraction isolates persistence so a database can be dropped in
  without touching the API.
- **Graceful failure.** Validation errors return `4xx`; parsing/processing
  problems are captured on the record (`status: FAILED`, `error: ...`) instead
  of surfacing stack traces.

---

## Learnings

- Measuring in geographic coordinates (degrees) is a common and silent
  correctness bug; choosing an appropriate projected CRS per dataset is the
  core of getting this right.
- KML files can contain multiple layers/folders, so enumerating layers and
  concatenating them yields more complete results than a single default read.
- Treating uploads as untrusted (size limits, zip-slip protection) matters even
  for a small service.

## Future Scope

- **Persistent storage** (SQLite/PostGIS) and retention/cleanup of uploads.
- **Asynchronous processing** with a task queue (e.g. Celery/RQ) for large
  files, with the existing status field driving a polling flow.
- **Smarter CRS selection** for datasets spanning multiple UTM zones — per
  feature projection, or an equal-area projection for global area totals.
- **More measurements** — perimeter, centroid, bounding box, geodesic
  (ellipsoidal) area/length as an alternative to projected measurement.
- **More input formats** — GeoJSON, GeoPackage, bare `.shp` sets.
- **Unit selection** — let clients request output in acres/hectares/kilometers.
- **Authentication, rate limiting, and tests/CI**.

---

## Submission

- Public GitHub repository: _add your repo URL here_.
