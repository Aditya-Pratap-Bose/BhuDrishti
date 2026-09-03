"""Schemas for the authenticated v2 ORI/DTM ingestion contract."""

from typing import Literal

from pydantic import BaseModel, Field


class RasterMetadata(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    bands: int = Field(gt=0)
    dtype: str
    crs: str
    bounds: list[float] = Field(min_length=4, max_length=4)
    resolution: list[float] = Field(min_length=2, max_length=2)


class RasterAsset(BaseModel):
    asset_id: str
    role: Literal["ori", "dtm"]
    format: Literal["COG"] = "COG"
    metadata: RasterMetadata


class RasterCoRegistration(BaseModel):
    valid: Literal[True] = True
    crs: str
    overlapping: Literal[True] = True


class RasterUploadResponse(BaseModel):
    """Metadata returned after both uploads have been validated and prepared."""

    type: Literal["RasterUpload"] = "RasterUpload"
    upload_id: str
    status: Literal["ready"] = "ready"
    ori: RasterAsset
    dtm: RasterAsset
    co_registration: RasterCoRegistration
