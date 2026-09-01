"""
app/core/config.py
-------------------
Central configuration loader.
Environment variables are loaded securely from .env.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App Meta ----
    APP_NAME: str = "BhuDrishti AI"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ---- Security / Auth ----
    SECRET_KEY: str = "bhudrishti-production-super-secret-jwt-key-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ---- Database (PostGIS) ----
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/bhudrishti"

    # ---- Colab AI Bridge ----
    COLAB_AI_ENDPOINT: str = "http://localhost:8000"
    COLAB_REQUEST_TIMEOUT_SECONDS: int = 180

    # ---- Local SAM engine ----
    LOCAL_SAM_CHECKPOINT: str = "models/sam_vit_b.pth"
    STAC_API_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    STAC_COLLECTION: str = "sentinel-2-l2a"
    STAC_DATE_RANGE: str = "2023-01-01/2026-08-26"
    STAC_MAX_CLOUD_COVER: float = 10.0
    LOCAL_UTM_EPSG: int = 32643

    # ---- Official ULPIN (Bhu-Aadhaar) ECCMA Standards ----
    # 14-character standard: SS (State) + DD (District) + TTT (Sub-District) + NNNNNNN (Vertex Hash)
    ULPIN_STATE_CODE: str = "22"          # Chhattisgarh (LGD State Code)
    ULPIN_DISTRICT_CODE: str = "10"       # Raipur District Code
    ULPIN_SUBDISTRICT_CODE: str = "001"   # Raipur Urban Tehsil Code

    # ---- Processing Engine Switch ('colab' or 'local') ----
    PROCESSING_MODE: str = "local"

    # ---- CORS ----
    CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()