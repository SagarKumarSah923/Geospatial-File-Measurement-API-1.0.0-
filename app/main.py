from contextlib import asynccontextmanager
from pathlib import Path
import json
import shutil
import tempfile
import uuid
import zipfile

import geopandas as gpd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base, FileRecord
from .schemas import FileInfoResponse, MeasurementResponse
from .services import process_geospatial_file

DATABASE_URL = "sqlite:///./geospatial.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Geospatial File Measurement API",
    version="1.0.0",
    description="Upload KML or zipped Shapefile data and calculate CRS-safe measurements.",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/files/", response_model=FileInfoResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".kml", ".zip"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a .kml or .zip containing a Shapefile.",
        )

    file_id = uuid.uuid4().hex
    work_dir = Path(tempfile.mkdtemp(prefix=f"{file_id}_", dir=str(UPLOAD_DIR)))
    source_path = work_dir / Path(filename).name

    try:
        with source_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        result = process_geospatial_file(source_path)

        with Session(engine) as db:
            record = FileRecord(
                id=file_id,
                filename=filename,
                feature_count=result["feature_count"],
                crs=result["crs"],
                status="COMPLETED",
                features_json=json.dumps(result["features"]),
                source_type=result["source_type"],
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to process geospatial file: {exc}",
        ) from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.get("/api/files/{file_id}/", response_model=FileInfoResponse)
def get_file(file_id: str):
    with Session(engine) as db:
        record = db.get(FileRecord, file_id)
        if not record:
            raise HTTPException(status_code=404, detail="File not found.")
        return record


@app.get("/api/files/{file_id}/measurements/", response_model=MeasurementResponse)
def get_measurements(file_id: str):
    with Session(engine) as db:
        record = db.get(FileRecord, file_id)
        if not record:
            raise HTTPException(status_code=404, detail="File not found.")

        features = json.loads(record.features_json)
        measurements = [
            {
                "feature_id": item["feature_id"],
                "geometry_type": item["geometry_type"],
                "measurement": item["measurement"],
            }
            for item in features
        ]

        return {
            "file_id": record.id,
            "filename": record.filename,
            "source_crs": record.crs,
            "measurements": measurements,
        }
