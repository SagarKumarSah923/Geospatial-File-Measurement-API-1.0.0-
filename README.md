# Geospatial File Measurement API

A production-oriented FastAPI backend for uploading KML files or ZIP archives containing a Shapefile, extracting geospatial features, and calculating CRS-safe measurements.

## Requirements

- Python 3.11+
- GDAL/OGR runtime libraries (required by GeoPandas/Pyogrio)
- Or Docker + Docker Compose

## Local setup

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open Swagger UI at `http://localhost:8000/docs`.

### Docker

```bash
docker compose up --build
```

## API

### 1. Upload and process

`POST /api/files/`

Multipart form field: `file`

Accepted:
- `.kml`
- `.zip` containing exactly one Shapefile (`.shp` plus its supporting files)

Example:

```bash
curl -X POST http://localhost:8000/api/files/ \
  -F "file=@survey.kml"
```

Response:

```json
{
  "id": "abc123...",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### 2. File information

`GET /api/files/{id}/`

Returns stored metadata for the processed file.

### 3. Measurements

`GET /api/files/{id}/measurements/`

Returns one measurement record per feature. Polygon/MultiPolygon features contain area in square meters; LineString/MultiLineString features contain length in meters; points and other unsupported geometries return `null` measurement values.

Example:

```json
{
  "file_id": "abc123...",
  "filename": "survey.kml",
  "source_crs": "EPSG:4326",
  "measurements": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "measurement": {
        "value": 123456.78,
        "unit": "square_meters",
        "calculation_crs": "EPSG:32643"
      }
    }
  ]
}
```

## Architecture

```text
Client
  |
  v
FastAPI endpoints
  |
  +--> upload validation
  |
  +--> GeoPandas / GDAL parsing
  |
  +--> CRS selection
  |      |
  |      +--> projected input: use source CRS
  |      +--> geographic input: estimate local UTM CRS
  |
  +--> Shapely measurements
  |
  +--> SQLite persistence
  |
  v
JSON API
```

### Application structure

- `app/main.py` — API routes, validation, persistence orchestration.
- `app/services.py` — geospatial parsing, CRS handling, measurements.
- `app/models.py` — SQLAlchemy persistence model.
- `app/schemas.py` — Pydantic response schemas.
- `tests/` — automated measurement tests.

## File-processing flow

1. Validate the extension.
2. Store the uploaded bytes in a temporary working directory.
3. For KML, load through GDAL/GeoPandas.
4. For ZIP, safely extract and locate the single `.shp` dataset.
5. Extract geometry, CRS, feature ID/index, and attributes.
6. Calculate measurements.
7. Store processed results and metadata in SQLite.
8. Remove the temporary upload directory.

## Measurement calculation

Measurements are performed on geometries transformed to a projected CRS.

- Polygon / MultiPolygon → area in square meters.
- LineString / MultiLineString → length in meters.
- Point → no measurement.
- Other geometry types → no measurement rather than crashing.

## CRS handling

Latitude/longitude coordinates in EPSG:4326 are angular degrees, so directly using Shapely's `.area` or `.length` would produce meaningless degree-based values.

For geographic CRS data, the service uses GeoPandas `estimate_utm_crs()` to select a local UTM projected CRS based on the dataset. The geometry is transformed with `to_crs()` before calculating area or length.

For an already-projected input, its projected CRS is used directly.

Files without a CRS are rejected because a safe measurement cannot be guaranteed.

## Design decisions

### Why FastAPI?

FastAPI provides typed request/response models, automatic OpenAPI documentation, and a clean async-friendly API surface.

### Why GeoPandas + Shapely + PyProj?

They provide mature support for common GIS formats, geometry operations, CRS transformations, and GDAL-backed I/O without requiring custom parsers.

### Why SQLite?

The assignment requires file lookup by ID. SQLite keeps the submission self-contained and demonstrates persistence without introducing operational database setup. PostgreSQL/PostGIS would be a natural production upgrade.

### Why store processed features as JSON?

The assignment focuses on measurement APIs rather than GIS database querying. Persisting the processed feature payload keeps the implementation compact. A PostGIS model would be preferable for large datasets or spatial queries.

### ZIP security

The implementation rejects absolute ZIP paths and only accepts archives containing one Shapefile dataset. Production deployments should additionally enforce upload-size limits, compression-ratio limits, authentication, rate limiting, and stronger archive validation.

## Error handling

- `400` — unsupported file type or invalid archive/content.
- `404` — unknown file ID.
- `422` — processing failure.
- Unsupported geometry measurement does not crash processing; its measurement is `null`.

## Testing

Run:

```bash
pytest -q
```

The tests verify that geographic-coordinate polygons produce square-meter areas and geographic-coordinate lines produce meter lengths.

## Learning

This project demonstrates:
- FastAPI API design
- Multipart file handling
- GeoPandas/GDAL data ingestion
- Shapely geometry operations
- PyProj CRS transformations
- SQLite persistence with SQLAlchemy
- API documentation and automated tests
- Dockerized deployment

## Future scope

- PostGIS for scalable spatial storage and spatial indexing.
- Background processing for very large uploads.
- Authentication and role-based access.
- Upload-size and rate limits.
- Async job status with `PROCESSING` / `COMPLETED` / `FAILED`.
- More geometry types and measurement modes.
- GeoJSON export and map visualization.
- Object storage such as S3 for original files.
- Observability with structured logging, metrics, and tracing.
