from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import AssistenteEntrada, AssistenteResposta, Mensagem

router = APIRouter(prefix="/api", tags=["Assistente"])


@router.post("/assistente", response_model=AssistenteResposta, summary="Perguntar ao AcessaCidade Helper",
             responses={429: {"model": Mensagem}})
async def assistente(request: Request, entrada: AssistenteEntrada):
    return await request.app.state.servicos.assistente.responder(entrada)
