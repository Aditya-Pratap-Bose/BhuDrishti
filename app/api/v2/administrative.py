"""Authenticated searchable India state and district endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.v2.administrative import AdministrativeListResponse
from app.services.v2.administrative import (
    CATALOG_SOURCE,
    list_districts,
    list_states,
    search_places,
)

router = APIRouter(prefix="/administrative", tags=["v2 Administrative Search"])


def _response(items: list[dict]) -> AdministrativeListResponse:
    return AdministrativeListResponse(items=items, total=len(items), source=CATALOG_SOURCE)


def _catalog_error(exc: Exception) -> HTTPException:
    del exc
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Administrative catalog is unavailable. Contact the system administrator.",
    )


@router.get("/states", response_model=AdministrativeListResponse)
def get_states(
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> AdministrativeListResponse:
    del current_user
    try:
        return _response(list_states(q, limit))
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise _catalog_error(exc)


@router.get("/states/{state_id}/districts", response_model=AdministrativeListResponse)
def get_districts(
    state_id: str,
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> AdministrativeListResponse:
    del current_user
    try:
        return _response(list_districts(state_id, q, limit))
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise _catalog_error(exc)


@router.get("/search", response_model=AdministrativeListResponse)
def search_administrative_places(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> AdministrativeListResponse:
    del current_user
    try:
        return _response(search_places(q, limit))
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise _catalog_error(exc)
