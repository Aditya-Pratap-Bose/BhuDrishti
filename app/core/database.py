"""
app/core/database.py
---------------------
SQLAlchemy + GeoAlchemy2 session engine for PostGIS.

IMPORTANT MINDSET: Ye file "lazy" hai — agar DATABASE_URL set nahi hai
.env me, toh engine None rahega aur app phir bhi chalu rahega (crash
nahi hoga). Sirf jab koi DB-wala endpoint hit hoga tab error milega,
poora server down nahi hoga. Ye demo-day safety net hai — agar Postgres
kabhi crash ho jaaye ya na chal paaye, baaki saara app (Colab bridge,
auth, health check) phir bhi zinda rahega.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
import logging

from app.core.config import settings

logger = logging.getLogger("bhudrishti.database")

Base = declarative_base()

engine = None
SessionLocal = None

if settings.DATABASE_URL:
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            # pool_pre_ping=True is critical: Postgres connections silently
            # die after idle time. Without this, first request after a
            # coffee break during the demo would throw a cryptic
            # "connection closed" error live on stage. This pings the
            # connection before using it and quietly reconnects if dead.
            pool_size=5,
            max_overflow=10,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Database engine initialized successfully.")
    except Exception as e:
        # Agar Postgres chalu hi nahi hai (e.g., tune abhi DB setup nahi kiya),
        # toh app crash nahi hoga — bas warning dega. Ye important hai kyunki
        # tera progress doc bolta hai DB abhi "explicitly deferred" hai.
        logger.warning(f"Database engine could not be created: {e}")
else:
    logger.warning(
        "DATABASE_URL not set in .env — running WITHOUT database. "
        "Parcel save/fetch endpoints will not work until you configure PostGIS."
    )


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — har request ko apna DB session milta hai,
    aur request khatam hote hi wo automatically close ho jaata hai
    (finally block me), even agar beech me error aa jaaye.

    Isse routes me use karenge: `db: Session = Depends(get_db)`
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL in your .env file "
            "and ensure PostgreSQL + PostGIS is running."
        )
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
    if engine is None:
        logger.warning("Skipping init_db() — no database engine configured.")
        return

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