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

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# NOTE ON SECURITY: Native bcrypt library directly industry-standard hashing
# rules follow karti hai. Ye algorithm deliberately slow (computationally heavy)
# banaya gaya hai taaki brute-force attacks completely impractical ban jayein.


def hash_password(plain_password: str) -> str:
    """
    Signup/registration ke waqt use hoga. Plain password kabhi bhi
    DB me nahi jaata — sirf ye hash jaata hai.
    """
    # String ko bytes me badalna zaroori hai kyunki bcrypt algorithm
    # sirf binary (raw bytes) data par hi perform karta hai.
    pwd_bytes = plain_password.encode("utf-8")
    
    # gensalt() har password ke liye ek unique random salt generate karta hai.
    # Isse "Rainbow Table" attacks (pre-computed hashes) completely useless ho jaate hain.
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
    
    # Database me readably store karne ke liye bytes ko wapas UTF-8 string me 
    # decode karke return karte hain (format looks like: $2b$12$...).
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Login ke waqt use hoga — user ne jo type kiya usse DB ke hash ke
    saath compare karta hai. Kabhi bhi hash ko decrypt nahi karta,
    bas dono taraf hash karke match check karta hai.
    """
    # Comparison ke liye dono plain text password aur database wale string hash
    # ko wapas bytes me convert karna mandatory hai.
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    
    # bcrypt.checkpw internally timing-attack safe comparison handle karta hai.
    # Yeh secure comparison ensure karta hai ki attacker executing time notice karke 
    # password ka partial match guess na kar sake.
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


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
