"""
app/core/database.py
---------------------
SQLAlchemy + GeoAlchemy2 session engine for PostGIS.

The API requires the configured database at startup. Database-backed
endpoints fail explicitly when persistence is unavailable; they never fall
back to process-local or in-memory state.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
import logging

from app.core.config import settings

logger = logging.getLogger("bhudrishti.database")

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logger.info("Database engine initialized successfully.")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — har request ko apna DB session milta hai,
    aur request khatam hote hi wo automatically close ho jaata hai
    (finally block me), even agar beech me error aa jaaye.

    Isse routes me use karenge: `db: Session = Depends(get_db)`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Sab models ke tables create karta hai agar already nahi hain.
    main.py ke startup event me call hoga.

    NOTE: Production me Alembic migrations use karni chahiye, lekin
    hackathon MVP ke liye ye direct create_all() approach fast aur
    sufficient hai — koi migration tooling setup ki zaroorat nahi.
    """
    # Import every model before create_all so tables added outside the existing
    # v1 route imports (including durable v2 jobs) are registered at startup.
    from app.models import job, parcel, user  # noqa: F401

    # PostGIS extension enable karna zaroori hai geometry columns ke liye.
    # Agar ye extension database me pehle se enabled nahi hai, geom column
    # create karte waqt silently fail ho sakta hai — isliye explicitly
    # yahan bhi ensure kar rahe hain.
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")
