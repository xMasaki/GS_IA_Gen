"""Rotas usadas pelo pipeline de dados (disciplina 02), protegidas por X-Pipeline-Token."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from ..schemas import Mensagem
from ..security import verificar_token

router = APIRouter(tags=["Pipeline de dados"])

MAX_GOLD_BYTES = 5 * 1024 * 1024
PROTEGIDA = {401: {"model": Mensagem}, 403: {"model": Mensagem}}


@router.get("/api/export/denuncias", summary="Exportação anonimizada (sem nome) em CSV ou JSON",
            responses={200: {"content": {"text/csv": {}, "application/json": {}}}, **PROTEGIDA})
def exportar(
    request: Request,
    formato: str = Query("csv", description="csv ou json"),
    x_pipeline_token: Optional[str] = Header(None, alias="X-Pipeline-Token"),
):
    s = request.app.state
    verificar_token(s.settings.pipeline_token, x_pipeline_token)
    formato = (formato or "csv").strip().lower()
    if formato == "json":
        return JSONResponse(s.servicos.exportacao.json(), headers={"Cache-Control": "no-store"})
    if formato == "csv":
        return Response(
            s.servicos.exportacao.csv().encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="denuncias_export.csv"', "Cache-Control": "no-store"},
        )
    raise HTTPException(status_code=422, detail="Formato inválido. Use formato=csv ou formato=json.")


@router.post("/api/pipeline/gold", summary="Publicar snapshot Gold (pipeline)",
             responses={413: {"model": Mensagem}, 422: {"model": Mensagem}, **PROTEGIDA})
async def publicar_gold(request: Request, x_pipeline_token: Optional[str] = Header(None, alias="X-Pipeline-Token")):
    s = request.app.state
    verificar_token(s.settings.pipeline_token, x_pipeline_token)
    corpo = bytearray()
    async for bloco in request.stream():
        corpo.extend(bloco)
        if len(corpo) > MAX_GOLD_BYTES:
            raise HTTPException(status_code=413, detail="Snapshot Gold grande demais (limite de 5 MB).")
    try:
        dados = json.loads(bytes(corpo).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="O corpo deve ser um JSON válido (UTF-8).") from None
    dados = s.servicos.gold.validar(dados)
    s.servicos.gold.salvar(dados)
    return {"mensagem": "Snapshot Gold publicado com sucesso.", "gerado_em": dados["gerado_em"]}
