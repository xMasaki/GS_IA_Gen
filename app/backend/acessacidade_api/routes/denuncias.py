from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, File, Form, Header, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse

from .. import domain as d
from ..repository import FiltrosListagem
from ..schemas import AlteracaoStatus, DenunciaCriada, DenunciaDetalhe, ListaDenuncias, Mensagem
from ..security import verificar_token
from ..services.denuncias import MSG_NAO_ENCONTRADA, erro_campo
from ..services.visao import STAGE_ORDER

router = APIRouter(prefix="/api/denuncias", tags=["Denúncias"])

CHUNK = 64 * 1024
ERROS_COMUNS = {
    404: {"model": Mensagem, "description": "Não encontrada"},
    422: {"description": "Dados inválidos (mensagens em português)"},
}


async def ler_foto(foto: UploadFile | str | None, max_bytes: int) -> bytes | None:
    """Lê o upload em blocos, rejeitando (413) assim que ultrapassar o limite."""
    if foto is None:
        return None
    if isinstance(foto, str):
        # Navegadores enviam o campo de arquivo vazio como parte sem nome de arquivo (texto vazio).
        if foto.strip():
            raise HTTPException(status_code=422, detail="Envie a fotografia como arquivo (JPEG, PNG ou WEBP).")
        return None
    partes: list[bytes] = []
    total = 0
    while True:
        bloco = await foto.read(CHUNK)
        if not bloco:
            break
        total += len(bloco)
        if total > max_bytes:
            await foto.close()
            raise HTTPException(
                status_code=413,
                detail=f"A fotografia ultrapassa o tamanho máximo permitido ({max_bytes / (1024 * 1024):.1f} MB).",
            )
        partes.append(bloco)
    await foto.close()
    if total == 0 and not (foto.filename or "").strip():
        return None  # campo de arquivo enviado vazio pelo navegador = sem foto
    return b"".join(partes)


@router.post(
    "", status_code=201, response_model=DenunciaCriada, summary="Registrar denúncia (multipart, foto opcional)",
    responses={413: {"model": Mensagem, "description": "Fotografia grande demais"},
               429: {"model": Mensagem, "description": "Limite de requisições"}, **ERROS_COMUNS},
)
async def criar_denuncia(
    request: Request,
    logradouro: str = Form(..., description="3–120 caracteres"),
    bairro: str = Form(..., description="2–80 caracteres"),
    tipo_obstaculo: str = Form(..., description="Chave da seção 3.1 (ex.: BURACO_CALCADA)"),
    descricao: str = Form(..., description="10–1000 caracteres"),
    impacto: str = Form(..., description="Chave da seção 3.2 (ex.: IMPEDE_PASSAGEM)"),
    consentimento: str = Form(..., description="Deve ser true"),
    nome: Optional[str] = Form(None, description="Opcional, até 80; NUNCA é retornado pela API"),
    numero: Optional[str] = Form(None, description="Até 10 caracteres (ex.: 120, S/N)"),
    cidade: Optional[str] = Form(None, description="Até 80; vazio = CIDADE_PADRAO"),
    ponto_referencia: Optional[str] = Form(None, description="Até 150 caracteres"),
    latitude: Optional[str] = Form(None, description="-90..90 (junto com longitude)"),
    longitude: Optional[str] = Form(None, description="-180..180 (junto com latitude)"),
    origem: Optional[str] = Form(None, description="WEB (padrão) ou RPA"),
    foto: Union[UploadFile, str, None] = File(None, description="JPEG/PNG/WEBP até MAX_UPLOAD_MB"),
):
    s = request.app.state
    campos = {
        "nome": nome, "logradouro": logradouro, "numero": numero, "bairro": bairro, "cidade": cidade,
        "ponto_referencia": ponto_referencia, "tipo_obstaculo": tipo_obstaculo, "descricao": descricao,
        "impacto": impacto, "latitude": latitude, "longitude": longitude, "consentimento": consentimento,
        "origem": origem,
    }
    dados_foto = await ler_foto(foto, s.settings.max_upload_bytes)
    return await s.servicos.denuncias.criar(campos, dados_foto)


@router.get("", response_model=ListaDenuncias, summary="Listar denúncias (paginado, mais recentes primeiro)")
def listar_denuncias(
    request: Request,
    status: Optional[str] = Query(None, description="Chave de status (seção 3.3)"),
    bairro: Optional[str] = Query(None, max_length=80, description="Contém, sem diferenciar maiúsculas"),
    tipo_obstaculo: Optional[str] = Query(None, description="Chave da seção 3.1"),
    protocolo: Optional[str] = Query(None, max_length=20),
    incluir_simulados: bool = Query(True),
    pagina: int = Query(1, ge=1, le=100000),
    limite: int = Query(20, ge=1, le=100),
):
    erros = []
    status_n = (status or "").strip().upper() or None
    tipo_n = (tipo_obstaculo or "").strip().upper() or None
    if status_n and status_n not in d.STATUS:
        erros.append(erro_campo("status", "Status inválido. Opções: " + ", ".join(d.STATUS) + ".", "query"))
    if tipo_n and tipo_n not in d.TIPOS_OBSTACULO:
        erros.append(erro_campo("tipo_obstaculo", "Tipo de obstáculo inválido. Opções: " + ", ".join(d.TIPOS_OBSTACULO) + ".", "query"))
    if erros:
        raise HTTPException(status_code=422, detail=erros)
    filtros = FiltrosListagem(
        status=status_n, bairro=(bairro or "").strip() or None, tipo_obstaculo=tipo_n,
        protocolo=(protocolo or "").strip().upper() or None, incluir_simulados=incluir_simulados,
    )
    return request.app.state.servicos.denuncias.listar(filtros, pagina, limite)


@router.get("/{ref}", response_model=DenunciaDetalhe, summary="Detalhe por id numérico ou protocolo",
            responses=ERROS_COMUNS)
def obter_denuncia(request: Request, ref: str = Path(..., max_length=40, description="Id (ex.: 12) ou protocolo (AC-2026-000012)")):
    return request.app.state.servicos.denuncias.obter(ref)


@router.get(
    "/{id}/imagens/{etapa}", summary="Imagem JPEG de uma etapa da triagem",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}, 404: {"model": Mensagem, "description": "Não encontrada"}},
)
def imagem_etapa(request: Request, id: int = Path(..., ge=1), etapa: str = Path(..., max_length=20)):
    if etapa not in STAGE_ORDER:
        raise HTTPException(status_code=404, detail="Etapa de imagem inválida. Use: " + ", ".join(STAGE_ORDER) + ".")
    svc = request.app.state.servicos
    row = svc.denuncias.repo.obter_por_id(id)
    if row is None:
        raise HTTPException(status_code=404, detail=MSG_NAO_ENCONTRADA)
    caminho = svc.visao.caminho_etapa(row["imagem_dir"], etapa)
    if caminho is None:
        raise HTTPException(status_code=404, detail="Esta denúncia não possui imagem para essa etapa.")
    return FileResponse(caminho, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@router.patch(
    "/{id}/status", response_model=DenunciaDetalhe, summary="Alterar status / revisão humana (equipe)",
    responses={401: {"model": Mensagem}, 403: {"model": Mensagem}, **ERROS_COMUNS},
)
def alterar_status(
    request: Request,
    corpo: AlteracaoStatus,
    id: int = Path(..., ge=1),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    verificar_token(request.app.state.settings.admin_token, x_admin_token)
    return request.app.state.servicos.denuncias.alterar_status(
        id, corpo.status, corpo.observacao, corpo.revisao_humana, "revisao_humana" in corpo.model_fields_set,
    )
