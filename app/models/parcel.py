"""
app/models/parcel.py
----------------------
The main spatial table — stores every AI-detected land parcel.
Matches the original blueprint schema exactly, with GeoAlchemy2 for
the PostGIS geometry column.

MINDSET: Ye table "source of truth" hai. Jo bhi Colab se GeoJSON aata
hai, wo yahan permanently store hota hai — taaki tu Colab tunnel band
karne ke baad bhi apna data khoye na. Frontend (Leaflet) yahi se data
padhega jab officer dobara login karega.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry

from app.core.database import Base


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    ulpin: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    # unique=True + index=True — ULPIN duplicate nahi ho sakta (govt-compliant
    # ID hai), aur index lagane se "search by ULPIN" instant hoga instead of
    # scanning poori table.

    area_sqm: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    perimeter_m: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    # Numeric(14, 2) — Decimal type, NOT Float. Ye important hai: floating-point
    # (Python float / SQL FLOAT) me rounding errors aate hain jo land-area jaisi
    # legal/government values ke liye acceptable nahi hote (2 sq.m ka fark bhi
    # dispute ban sakta hai revenue records me). Numeric = exact decimal math.

    land_use_type: Mapped[str] = mapped_column(
        String(50), default="Unclassified", nullable=False
    )

    owner_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Attribute Inspector drawer se officer manually bharega — AI isse
    # kabhi generate nahi karta, ye hamesha human-entered hoga.

    # ---- THE ACTUAL SPATIAL COLUMN ----
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    # srid=4326 = WGS84 (plain lat/long) — matches tera blueprint aur
    # tera Colab pipeline jo already area-calc UTM (32643) me karke wapas
    # 4326 me convert karta hai delivery ke liye. Ye consistency critical hai:
    # agar frontend (Leaflet) aur DB alag SRID expect karein, polygons
    # galat jagah render honge ya bilkul dikhenge hi nahi.
    #
    # spatial_index=True yahan set kiya hai (GeoAlchemy2 automatically
    # GIST index bana dega) — matches tera blueprint ka
    # `CREATE INDEX idx_parcels_spatial_geom ON parcels USING GIST (geom)`
    # bina manually SQL likhe.

    # ---- Audit trail: kisne banaya ----
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Nullable rakha hai jaan-bujh ke: agar koi parcel bulk-import/script se
    # aaya (koi logged-in user ke bina), insert fail nahi hoga.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # onupdate — jab bhi koi officer Leaflet-Draw se polygon reshape karega
    # (edit), ye automatically refresh hoga — audit ke liye "last modified"
    # track karna zaroori hai govt records me.

    __table_args__ = (
        # Extra composite index — land_use_type + created_at pe filter/sort
        # karna common hoga dashboard me ("show me all Residential plots
        # added this week"). Ye query ko fast rakhega jaise-jaise data badhega.
        Index("idx_parcel_landuse_date", "land_use_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Parcel {self.ulpin} ({self.area_sqm} sqm)>"