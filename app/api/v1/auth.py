"""
app/api/v1/auth.py
--------------------
Register, Login, and "Who am I" endpoints. Also defines
`get_current_user` — the dependency every other protected route
(drone.py, satellite.py, parcel.py) will import and use.

MINDSET: Ye file "gatekeeper" hai. Har protected endpoint bolega
"pehle mujhe batao ye request kaun bhej raha hai" — aur wo answer
yahin se aayega.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import uuid

from app.core.config import settings
from app.core.database import get_db, get_db_optional
from app.models.user import User, UserRole
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# tokenUrl sirf Swagger UI (/docs) ke "Authorize" button ke liye use hota
# hai — batata hai ki token kahan se milega. Actual verification neeche
# get_current_user karega.
# auto_error=False zaroori hai — warna FastAPI Authorization header na
# hone par khud hi 401 de dega, get_current_user ke andar tak pahunchega
# hi nahi, aur disabled-mode ka check kabhi chalega hi nahi.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ---------------------------------------------------------------------
# REGISTER
# ---------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Naya survey official register karta hai. Success pe seedha login
    kar deta hai (token de deta hai) — taaki registration ke baad
    ek alag login step na karna pade demo me.
    """
    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        department=payload.department,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Ye tab trigger hoga jab email already DB me unique constraint
        # todta hai (duplicate registration). Bina isके catch kiye,
        # user ko raw Postgres error dikhta jo confusing aur unprofessional
        # lagta — especially live demo me judges ke saamne.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Is email se already ek account exist karta hai.",
        )
    db.refresh(new_user)

    token = create_access_token(subject=str(new_user.id), extra_claims={"role": new_user.role.value})

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(new_user),
    )


# ---------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Email + password verify karke JWT token deta hai.
    """
    user = db.query(User).filter(User.email == payload.email).first()

    # IMPORTANT: Jaan-bujh ke ek hi generic error message hai chahe
    # email exist na kare, ya password galat ho. Agar hum alag-alag
    # bolte ("email not found" vs "wrong password"), attacker ko pata
    # chal jaata ki konse emails registered hain (user enumeration
    # attack) — govt system ke liye ye risk acceptable nahi.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email ya password galat hai.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise invalid_credentials

    if not verify_password(payload.password, user.hashed_password):
        raise invalid_credentials

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ye account deactivate kar diya gaya hai. Admin se contact karein.",
        )

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------
# CURRENT USER DEPENDENCY — baaki sab routes ye import karenge
# ---------------------------------------------------------------------

def _demo_user() -> User:
    """
    AUTH_MODE=disabled ke waqt ye ek fake 'Demo Officer' return karta
    hai — kabhi DB me save nahi hota, sirf memory me hota hai taaki
    baaki saara code (jo current_user.email, current_user.role maangta
    hai) bina badle chal sake.
    """
    return User(
        id=uuid.uuid4(),
        full_name="Demo Officer",
        email="demo@bhudrishti.local",
        hashed_password="not-used-in-demo-mode",
        role=UserRole.SURVEYOR,
        department="SSIPMT Test Lab",
        is_active=True,
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session | None = Depends(get_db_optional),
) -> User:
    if settings.AUTH_MODE == "disabled":
        # DB ko haath tak nahi lagaya — seedha demo officer de diya.
        return _demo_user()

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials invalid ya expired hain.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_MODE=enabled hai lekin database configure nahi hai.",
        )

    if token is None:
        raise credentials_error

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_error

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivate hai.")

    return user


def require_role(*allowed_roles):
    """
    Role-based access control ke liye ek chhota factory function.
    Usage example (drone.py/parcel.py me):

        @router.delete("/{parcel_id}")
        def delete_parcel(
            current_user: User = Depends(require_role("admin", "tehsildar"))
        ):
            ...

    Isse "sirf Admin/Tehsildar delete kar sakte hain, Surveyor nahi"
    jaisi government-appropriate restrictions easily lag jaayengi.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ye action sirf {', '.join(allowed_roles)} kar sakte hain.",
            )
        return current_user
    return role_checker


# ---------------------------------------------------------------------
# WHO AM I
# ---------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Frontend page-load pe ye call karke pata karega "kaun logged in hai"
    — token se hi puri profile mil jaati hai, kisi extra DB call ki
    zaroorat nahi frontend ki taraf se.
    """
    return current_user