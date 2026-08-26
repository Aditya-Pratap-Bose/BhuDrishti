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
    # Abhi optional rakha hai kyunki DB wiring baad me hogi (jaisa progress doc me tha).
    DATABASE_URL: str | None = None

    # ---- Colab AI Bridge ----
    # YE SABSE IMPORTANT VARIABLE HAI. Har naye Colab session me
    # cloudflared/zrok2 se naya URL milega — bas isse .env me paste karo,
    # code me kahin chhedne ki zaroorat nahi.
    COLAB_AI_ENDPOINT: str = "http://localhost:8000"
    COLAB_REQUEST_TIMEOUT_SECONDS: int = 180  # SAM inference slow ho sakta hai, patience rakho

    # ---- CORS ----
    # Frontend (Leaflet dashboard) yahi se allow hoga
    CORS_ORIGINS: list[str] = ["*"]  # Hackathon ke liye theek hai, production me tighten karna

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