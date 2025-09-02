from __future__ import annotations

from fastapi import APIRouter
from apps.api.schemas.health import HealthStatus

router = APIRouter(prefix="/health", tags=["health"]) 


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
def ready() -> HealthStatus:
    return HealthStatus(status="ready")


