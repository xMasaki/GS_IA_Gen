from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..schemas import Indicadores

router = APIRouter(prefix="/api/indicadores", tags=["Indicadores"])


@router.get("", response_model=Indicadores, summary="Indicadores operacionais (tempo real, SQLite)")
def indicadores(request: Request, incluir_simulados: bool = Query(True)):
    return request.app.state.servicos.indicadores.calcular(incluir_simulados)


@router.get("/analiticos", summary="Último snapshot Gold publicado pelo pipeline")
def analiticos(request: Request) -> dict:
    return request.app.state.servicos.gold.carregar()
