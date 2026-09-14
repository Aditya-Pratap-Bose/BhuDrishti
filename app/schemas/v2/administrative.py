"""API contracts for searchable India administrative metadata."""

from pydantic import BaseModel, Field, field_validator, model_validator
from shapely.geometry import shape


class AdministrativePlace(BaseModel):
    id: str
    name: str
    level: str
    state_id: str | None = None
    state_name: str | None = None
    district_id: str | None = None
    district_name: str | None = None
    bbox: list[float] = Field(..., min_length=4, max_length=4)


class AdministrativeListResponse(BaseModel):
    items: list[AdministrativePlace]
    total: int
    source: str


class SurveyAoiUpdate(BaseModel):
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    geometry: dict | None = None
    source: str = Field(default="map_bounds", min_length=2, max_length=32)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float]) -> list[float]:
        if not all(isinstance(item, (int, float)) for item in value):
            raise ValueError("bbox must contain numeric coordinates")
        min_lon, min_lat, max_lon, max_lat = value
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise ValueError("bbox must be ordered and within WGS84 coordinate bounds")
        return [float(item) for item in value]

    @model_validator(mode="after")
    def validate_aoi(self) -> "SurveyAoiUpdate":
        if self.geometry is None and self.bbox is None:
            raise ValueError("either bbox or geometry is required")
        if self.geometry is not None:
            if self.geometry.get("type") != "Polygon":
                raise ValueError("AOI geometry must be a GeoJSON Polygon")
            try:
                polygon = shape(self.geometry)
            except (TypeError, ValueError) as exc:
                raise ValueError("AOI geometry is not valid GeoJSON") from exc
            if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
                raise ValueError("AOI polygon must be valid and non-empty")
            min_lon, min_lat, max_lon, max_lat = polygon.bounds
            if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
                raise ValueError("AOI polygon must use WGS84 longitude/latitude bounds")
            self.bbox = [float(min_lon), float(min_lat), float(max_lon), float(max_lat)]
        return self
