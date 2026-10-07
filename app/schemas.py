from typing import Any
from pydantic import BaseModel, ConfigDict


class FileInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    feature_count: int
    crs: str
    status: str


class FeatureMeasurement(BaseModel):
    feature_id: int
    geometry_type: str
    measurement: Any


class MeasurementResponse(BaseModel):
    file_id: str
    filename: str
    source_crs: str
    measurements: list[FeatureMeasurement]
