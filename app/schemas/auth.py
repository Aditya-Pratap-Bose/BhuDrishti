"""
app/schemas/auth.py
---------------------
Pydantic schemas for authentication — Register, Login, Token response,
and the "safe" User response (never exposes hashed_password).

MINDSET: In-DB model (app/models/user.py) aur outside-world response
kabhi ek jaisi cheez nahi honi chahiye. Agar humne seedha User model
return kar diya kisi endpoint se, hashed_password bhi JSON me chala
jaayega — ye ek chhoti si galti govt system me bahut bada security
incident ban sakti hai. Isliye har response ek "shield" schema se
guzarta hai jo sirf safe fields expose karta hai.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserRole


# ---------------------------------------------------------------------
# INPUT SCHEMAS (request bodies)
# ---------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """
    Naye survey official ko system me register karne ke liye.
    """
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    # EmailStr automatically format validate karta hai — agar koi
    # "abc123" bhej de email field me, Pydantic khud 422 de dega,
    # tujhe manual regex likhne ki zaroorat nahi.

    password: str = Field(min_length=8, max_length=128)
    # min_length=8 — bahut basic lekin zaroori check. Chhota sa gate
    # hai kamzor passwords ke against.

    role: UserRole = UserRole.SURVEYOR
    department: str | None = Field(default=None, max_length=150)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------------------------------------------------------------------
# OUTPUT SCHEMAS (responses)
# ---------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Safe user data jo frontend ko dikhaya ja sakta hai — kabhi bhi
    hashed_password isme nahi hoga.
    """
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    department: str | None
    is_active: bool
    created_at: datetime

    # from_attributes=True zaroori hai kyunki hum seedha SQLAlchemy
    # User object isme pass karenge (ORM object), Pydantic ko batana
    # padta hai "attributes se read karo, dict se nahi".
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """
    Login/Register success ke baad ye return hota hai — frontend isko
    localStorage/cookie me save karke har request ke saath bhejega.
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    # user bhi saath me bhej diya taaki frontend ko login ke turant baad
    # ek extra /me API call na karni pade role/name dikhane ke liye —
    # demo me ek round-trip kam, thoda snappier feel dega.