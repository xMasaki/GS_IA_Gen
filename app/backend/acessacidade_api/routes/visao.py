from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..schemas import AnaliseVisao, Mensagem
from .denuncias import ler_foto

router = APIRouter(prefix="/api/visao", tags=["Visão computacional"])


@router.post(
    "/analisar", response_model=AnaliseVisao, summary="Analisar uma foto sem salvar nada",
    responses={413: {"model": Mensagem}, 422: {"model": Mensagem}, 429: {"model": Mensagem}},
)
async def analisar(request: Request, foto: UploadFile = File(..., description="JPEG/PNG/WEBP")):
    s = request.app.state
    dados = await ler_foto(foto, s.settings.max_upload_bytes)
    if not dados:
        raise HTTPException(status_code=422, detail="Nenhuma imagem foi enviada (arquivo vazio).")
    triagem = await run_in_threadpool(s.servicos.visao.triar, dados)
    corpo = triagem.visao_dict()
    corpo["imagens"] = s.servicos.visao.data_uris(triagem.etapas_jpeg)
    return corpo
