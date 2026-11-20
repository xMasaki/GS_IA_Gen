"""Integração com o AcessaCidade Helper (contrato, seções 4.9 e 6).

O helper não acessa o banco: aqui buscamos a denúncia pelo protocolo (campo `protocolo`
ou o primeiro protocolo encontrado na mensagem) e a entregamos já no formato público.
"""
from __future__ import annotations

import logging
from typing import Any

from starlette.concurrency import run_in_threadpool

from .. import domain as d
from ..config import Settings
from ..metrics import Metricas
from ..schemas import AssistenteEntrada
from .denuncias import ServicoDenuncias
from .indicadores import ServicoIndicadores

logger = logging.getLogger("acessacidade.assistente")

try:
    from acessacidade_helper import AssistantRequest, AssistantService, extract_protocol
    HELPER_DISPONIVEL = True
except Exception:  # pragma: no cover
    AssistantRequest = AssistantService = None  # type: ignore[assignment]
    HELPER_DISPONIVEL = False

    def extract_protocol(texto):  # type: ignore[no-redef]
        import re
        m = re.search(r"AC-\d{4}-\d{6}", texto or "", re.IGNORECASE)
        return m.group(0).upper() if m else None

RESPOSTA_INDISPONIVEL = (
    "O assistente está temporariamente indisponível. Você pode consultar sua denúncia na tela "
    "\"Consultar\" usando o protocolo (formato AC-AAAA-NNNNNN)."
)


class ServicoAssistente:
    def __init__(self, settings: Settings, denuncias: ServicoDenuncias, indicadores: ServicoIndicadores,
                 metricas: Metricas) -> None:
        self.denuncias = denuncias
        self.indicadores = indicadores
        self.metricas = metricas
        self.svc = None
        if HELPER_DISPONIVEL:
            try:
                self.svc = AssistantService.from_env(dict(settings.env))
            except Exception:  # configuração inválida não derruba a API
                logger.exception("falha ao iniciar o assistente", extra={"evento": "assistente_init_falhou"})
                self.svc = None
        self.opcoes = {
            "tipo_obstaculo": d.lista_opcoes(d.TIPOS_OBSTACULO),
            "impacto": d.lista_opcoes(d.IMPACTOS),
            "status": d.lista_opcoes(d.STATUS, d.STATUS_SIGNIFICADO),
            "classificacao_visao": d.lista_opcoes(d.CLASSIFICACOES_VISAO),
        }

    @property
    def modo(self) -> str:
        return "llm" if self.svc is not None and self.svc.llm_enabled else "fallback"

    def _responder_sync(self, entrada: AssistenteEntrada) -> dict[str, Any]:
        protocolo = entrada.protocolo or extract_protocol(entrada.mensagem)
        denuncia = self.denuncias.buscar_por_protocolo(protocolo) if protocolo else None
        if self.svc is None:
            return {"resposta": RESPOSTA_INDISPONIVEL, "fonte": "fallback", "modelo": None,
                    "denuncia_referenciada": None, "avisos": ["Assistente em modo básico."]}
        try:
            indicadores = self.indicadores.resumo(True)
        except Exception:
            indicadores = None
        req = AssistantRequest(
            mensagem=entrada.mensagem,
            modo=entrada.modo,
            historico=[h.model_dump() for h in entrada.historico[-6:]],
            denuncia=denuncia,
            protocolo_solicitado=protocolo,
            indicadores=indicadores,
            opcoes=self.opcoes,
            contexto_tela=entrada.contexto_tela,
        )
        resp = self.svc.answer(req)
        referenciada = getattr(resp, "denuncia_referenciada", None)
        if denuncia is None:
            referenciada = None  # nunca referenciar uma denúncia que não existe
        elif not referenciada:
            referenciada = denuncia["protocolo"]
        return {
            "resposta": resp.resposta,
            "fonte": resp.fonte if resp.fonte in ("llm", "fallback") else "fallback",
            "modelo": resp.modelo,
            "denuncia_referenciada": referenciada,
            "avisos": list(resp.avisos or []),
        }

    async def responder(self, entrada: AssistenteEntrada) -> dict[str, Any]:
        try:
            resultado = await run_in_threadpool(self._responder_sync, entrada)
        except Exception:
            logger.exception("erro no assistente", extra={"evento": "assistente_erro"})
            resultado = {"resposta": RESPOSTA_INDISPONIVEL, "fonte": "fallback", "modelo": None,
                         "denuncia_referenciada": None, "avisos": ["Ocorreu um erro ao gerar a resposta."]}
        self.metricas.assistente_respostas_total.labels(resultado["fonte"]).inc()
        logger.info("assistente respondeu", extra={"evento": "assistente_resposta", "fonte": resultado["fonte"],
                                                   "modo": entrada.modo,
                                                   "com_protocolo": bool(resultado["denuncia_referenciada"])})
        return resultado
