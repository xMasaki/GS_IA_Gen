from __future__ import annotations

from fastapi import APIRouter, Request

from .. import domain as d
from ..services.visao import STAGE_ORDER

router = APIRouter(prefix="/api/meta", tags=["Metadados"])


@router.get("/opcoes", summary="Enumerações com rótulos (tipos, impactos, status, classificações, origens)")
def opcoes(request: Request) -> dict:
    return d.opcoes(request.app.state.settings.max_upload_mb, tuple(STAGE_ORDER))
