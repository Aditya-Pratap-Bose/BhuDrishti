"""
app/api/v2/reconciliation.py
----------------------------
Authenticated endpoints for comparing AI-generated parcels with authoritative historical land records.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.services.v2.reconciliation import reconcile_cadastral_parcels

logger = logging.getLogger("bhudrishti.api.v2.reconciliation")

router = APIRouter(prefix="/reconciliation", tags=["v2 Cadastral Reconciliation"])


class ReconciliationRequest(BaseModel):
    existing_parcels: list[dict[str, Any]] = Field(..., description="Authoritative historical cadastral features")
    ai_parcels: list[dict[str, Any]] = Field(..., description="Newly extracted AI parcel features")
    match_iou_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    minor_iou_threshold: float = Field(default=0.60, ge=0.3, le=0.9)


@router.post("/compare")
def compare_cadastral_parcels(
    payload: ReconciliationRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Compare AI parcels against existing cadastral vectors.
    Classifies differences into MATCH, MINOR_CHANGE, MAJOR_CHANGE, NEW, MISSING, CONFLICT.
    """
    del current_user
    report = reconcile_cadastral_parcels(
        existing_parcels=payload.existing_parcels,
        ai_parcels=payload.ai_parcels,
        match_iou_threshold=payload.match_iou_threshold,
        minor_iou_threshold=payload.minor_iou_threshold,
    )
    return report.to_dict()
