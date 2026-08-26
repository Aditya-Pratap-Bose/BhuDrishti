"""
app/core/security.py
----------------------
Password hashing (bcrypt) + JWT token creation/verification.

MINDSET: Ye file kabhi bhi plain-text password store/compare nahi
karti. Har password bcrypt se hash hota hai (one-way — kabhi wapas
decrypt nahi ho sakta), aur login sirf hash-compare se validate hota
hai. Agar kal database leak bhi ho jaaye, attacker ko real passwords
nahi milenge.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt scheme — industry standard, deliberately slow (isse hi brute-force
# attacks impractical ban jaate hain). "auto" deprecated hashes ko bhi
# handle kar leta hai future-proofing ke liye.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Signup/registration ke waqt use hoga. Plain password kabhi bhi
    DB me nahi jaata — sirf ye hash jaata hai.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Login ke waqt use hoga — user ne jo type kiya usse DB ke hash ke
    saath compare karta hai. Kabhi bhi hash ko decrypt nahi karta,
    bas dono taraf hash karke match check karta hai.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Login successful hone ke baad ye token banega. Frontend isse
    localStorage/cookie me store karega aur har request ke Authorization
    header me bhejega: `Bearer <token>`.

    `subject` = usually user ka unique ID ya username.
    `extra_claims` = optional extra data (e.g. role: "tehsildar")
                     jo token ke andar embed karna ho.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,       # issued-at — kab bana token
        "exp": expire,    # expiry — kab tak valid hai
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Incoming request ke token ko verify karta hai. Agar token invalid,
    tampered, ya expired hai — None return karta hai (crash nahi karta).
    Caller (auth dependency) decide karega ki 401 dena hai ya nahi.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        # Ye ek hi except block jaan-bujh ke sabhi JWT errors
        # (expired, malformed, wrong signature) ko catch karta hai —
        # security ke liye hum attacker ko exact reason nahi batate
        # ki token kyun fail hua (info leakage se bachne ke liye).
        return None