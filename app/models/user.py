"""
app/models/user.py
--------------------
User table — stores login credentials + role for access control.

MINDSET: Government system hai, isliye role-based access zaroori hai.
Ek Surveyor field data upload kar sakta hai, lekin sirf ek Admin/Tehsildar
hi parcels ko "approve" ya "delete" kar sakta hai. Role abhi simple
string enum hai — future me granular permissions table bhi ban sakti hai,
lekin hackathon MVP ke liye ye kaafi hai.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    """
    str + enum.Enum dono se inherit karna zaroori hai — isse Pydantic
    aur SQLAlchemy dono ise seedha JSON string ki tarah treat karte hain
    (e.g. "admin"), instead of ugly "UserRole.ADMIN" wrapper object.
    """
    ADMIN = "admin"
    TEHSILDAR = "tehsildar"
    SURVEYOR = "surveyor"
    PATWARI = "patwari"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # index=True zaroori hai — login har baar email se lookup karega.
    # Bina index ke, jaise jaise users badhenge, login slow hota jayega
    # (full table scan). Demo me shayad na dikhe (kam users), lekin
    # judges agar "scalability" pucche toh ye correct answer hai.

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # KABHI bhi plain password column mat banana. Sirf hash store hoga —
    # security.py ka hash_password() isko fill karega.

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.SURVEYOR,
        nullable=False,
    )

    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # e.g. "Raipur District Revenue Office" — optional but useful for
    # government context / audit trail.