"""
app/core/config.py
-------------------
Central configuration loader.
Sab environment variables yahin se aate hain — kahin bhi hardcoded
secret ya URL nahi hona chahiye, warna demo din URL badalne pe
10 files edit karni padengi. Sirf .env change karo, kaam ho jayega.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ---- App Meta ----
    APP_NAME: str = "BhuDrishti AI"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # ---- Security / Auth ----
    SECRET_KEY: str  # .env me daalna zaroori hai — no default, taaki kabhi bhoolo na
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours — demo ke beech logout na ho

    # ---- Database (PostGIS) ----
    # Production runs against PostgreSQL + PostGIS. A missing URL must fail
    # startup instead of leaving auth and registry endpoints unusable.
    DATABASE_URL: str

    # ---- Colab AI Bridge ----
    # YE SABSE IMPORTANT VARIABLE HAI. Har naye Colab session me
    # cloudflared/zrok2 se naya URL milega — bas isse .env me paste karo,
    # code me kahin chhedne ki zaroorat nahi.
    COLAB_AI_ENDPOINT: str = "http://localhost:8000"
    COLAB_REQUEST_TIMEOUT_SECONDS: int = 180  # SAM inference slow ho sakta hai, patience rakho
    
    # ---- Local SAM engine ----
    # This path is used only when PROCESSING_MODE=local. Keep the large model
    # outside the repository and point this setting at the downloaded file.
    LOCAL_SAM_CHECKPOINT: str = "models/sam_vit_b.pth"
    STAC_API_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    STAC_COLLECTION: str = "sentinel-2-l2a"
    STAC_DATE_RANGE: str = "2023-01-01/2026-08-26"
    STAC_MAX_CLOUD_COVER: float = 10.0
    LOCAL_UTM_EPSG: int = 32643

    # ---- Processing Engine Switch ----
    # "colab" = abhi wala setup (Cloudflare tunnel se Colab GPU tak).
    # "local" = future mein jab apna GPU server ho, bina code chhede
    # switch karne ke liye. Sirf .env mein ye ek line badalni hogi,
    # server restart karo, done — demo-day ke liye life-saver.
    PROCESSING_MODE: str = "colab"

    # ---- CORS ----
    # Same-origin serving needs no CORS entry. Keep this for an approved
    # separately hosted frontend origin.
    CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    lru_cache lagaya hai taaki .env baar baar disk se na padhe har request pe —
    ek baar load hoga, phir memory se serve hoga. Chhota optimization hai
    lekin demo ke time har millisecond count hota hai.
    """
    return Settings()


settings = get_settings()