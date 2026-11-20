"""Integração com o pacote de visão computacional ``acessacidade_vision`` (contrato, seção 5)."""
from __future__ import annotations

import base64
import logging
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..config import Settings
from ..metrics import Metricas

logger = logging.getLogger("acessacidade.visao")

try:  # o backend continua de pé (sem triagem) se o pacote não estiver disponível
    import acessacidade_vision as _vision
    from acessacidade_vision import STAGE_ORDER, VisionError
    VISAO_DISPONIVEL = True
except Exception:  # pragma: no cover - ambiente sem OpenCV
    _vision = None
    STAGE_ORDER = ("original", "cinza", "filtrada", "contraste", "bordas", "mascara", "contornos")
    VISAO_DISPONIVEL = False

    class VisionError(Exception):  # type: ignore[no-redef]
        code = "UNAVAILABLE"
        message = "Triagem indisponível."

_UUID_HEX = set("0123456789abcdef-")


@dataclass
class ResultadoTriagem:
    resultado: Any               # AnalysisResult
    etapas_jpeg: dict[str, bytes]

    def visao_dict(self) -> dict:
        """to_dict() do pacote (sem imagens), pronto para persistir em JSON."""
        return self.resultado.to_dict()


class ServicoVisao:
    def __init__(self, settings: Settings, metricas: Metricas) -> None:
        self.settings = settings
        self.metricas = metricas

    @property
    def disponivel(self) -> bool:
        return VISAO_DISPONIVEL

    # -------------------------------------------------------------- triagem
    def triar(self, dados: bytes) -> ResultadoTriagem:
        """Valida → sanitiza → analisa (sobre a imagem sanitizada). Síncrono: chamar em threadpool.

        Levanta HTTPException 413/422/503 com mensagem em português.
        """
        if not VISAO_DISPONIVEL:
            raise HTTPException(status_code=503, detail="A triagem de fotografias está indisponível no momento.")
        inicio = time.perf_counter()
        try:
            _vision.validate_image_bytes(dados, self.settings.max_upload_bytes)
            sanitizada = _vision.sanitize_image(dados)
            resultado = _vision.analyze_image(sanitizada)
            etapas = resultado.encode_stages(".jpg", 85)
        except VisionError as exc:
            codigo = getattr(exc, "code", "INVALID_IMAGE")
            logger.info("foto rejeitada", extra={"evento": "foto_rejeitada", "codigo": codigo})
            status = 413 if codigo == "FILE_TOO_LARGE" else 422
            raise HTTPException(status_code=status, detail=getattr(exc, "message", str(exc))) from None
        finally:
            self.metricas.visao_duracao_seconds.observe(time.perf_counter() - inicio)
        self.metricas.visao_classificacoes_total.labels(resultado.classification).inc()
        return ResultadoTriagem(resultado=resultado, etapas_jpeg=etapas)

    # -------------------------------------------------------------- arquivos
    def salvar_etapas(self, triagem: ResultadoTriagem) -> str:
        """Grava DATA_DIR/uploads/<uuid4>/<etapa>.jpg e devolve o nome da pasta."""
        pasta_nome = uuid.uuid4().hex
        destino = self.settings.uploads_dir / pasta_nome
        destino.mkdir(parents=True, exist_ok=False)
        try:
            for etapa in STAGE_ORDER:
                conteudo = triagem.etapas_jpeg.get(etapa)
                if conteudo:
                    (destino / f"{etapa}.jpg").write_bytes(conteudo)
        except OSError:
            shutil.rmtree(destino, ignore_errors=True)
            raise
        return pasta_nome

    def remover_pasta(self, pasta_nome: str | None) -> None:
        if pasta_nome and set(pasta_nome) <= _UUID_HEX:
            shutil.rmtree(self.settings.uploads_dir / pasta_nome, ignore_errors=True)

    def caminho_etapa(self, pasta_nome: str | None, etapa: str) -> Path | None:
        """Caminho seguro de uma etapa: etapa validada contra STAGE_ORDER e pasta = uuid hex."""
        if not pasta_nome or etapa not in STAGE_ORDER or not set(pasta_nome) <= _UUID_HEX:
            return None
        base = self.settings.uploads_dir.resolve()
        caminho = (base / pasta_nome / f"{etapa}.jpg").resolve()
        if base not in caminho.parents or not caminho.is_file():
            return None
        return caminho

    @staticmethod
    def urls_etapas(denuncia_id: int) -> dict[str, str]:
        return {e: f"/api/denuncias/{denuncia_id}/imagens/{e}" for e in STAGE_ORDER}

    @staticmethod
    def data_uris(etapas_jpeg: dict[str, bytes]) -> dict[str, str]:
        return {
            e: "data:image/jpeg;base64," + base64.b64encode(etapas_jpeg[e]).decode("ascii")
            for e in STAGE_ORDER if e in etapas_jpeg
        }
