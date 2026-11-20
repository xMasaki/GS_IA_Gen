"""Serviço principal do AcessaCidade Helper (interface da seção 6 do contrato)."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

import httpx

from . import fallback
from .config import HelperConfig
from .context import (
    ContextoPreparado,
    denuncia_segura,
    indicadores_seguros,
    montar_mensagem_dados,
    sanear_historico,
    texto_enumeracoes,
    texto_significado_status,
)
from .domain import MODOS
from .guardrails import (
    AVISO_DADOS_PESSOAIS,
    AVISO_FALHA_LLM,
    AVISO_GUARDRAIL,
    AVISO_IA_GERATIVA,
    AVISO_MODO_BASICO,
    AVISO_MODO_INVALIDO,
    AVISO_NAO_OFICIAL,
    AVISO_SIMULADO,
    AVISO_TRIAGEM,
    AVISO_TRUNCADO,
    MAX_MENSAGEM,
    extract_protocol,
    limitar_resposta,
    menciona_nao_encontrado,
    preparar_texto_nao_confiavel,
    protocolo_valido,
    protocolos_no_texto,
    verificar_resposta_llm,
)
from .llm_client import LLMError, OpenRouterClient
from .prompts import PromptError, PromptLibrary

logger = logging.getLogger("acessacidade_helper")


@dataclass
class AssistantRequest:
    mensagem: str
    modo: str = "geral"
    historico: list[dict] = field(default_factory=list)
    denuncia: dict | None = None
    protocolo_solicitado: str | None = None
    indicadores: dict | None = None
    opcoes: dict | None = None
    contexto_tela: str | None = None


@dataclass
class AssistantResponse:
    resposta: str
    fonte: str  # "llm" | "fallback"
    modelo: str | None = None
    avisos: list[str] = field(default_factory=list)
    denuncia_referenciada: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dedup(itens: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in itens if i))


class AssistantService:
    """Responde perguntas sobre o AcessaCidade com LLM (se configurado) ou por regras.

    ``answer`` nunca levanta exceção para entradas comuns: qualquer falha do LLM vira
    resposta ``fonte="fallback"`` com aviso.
    """

    def __init__(
        self,
        config: HelperConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        prompts: PromptLibrary | None = None,
    ) -> None:
        self.config = config or HelperConfig()
        self.motivo_modo_basico: str | None = None
        self.prompts: PromptLibrary | None = prompts
        if self.prompts is None:
            try:
                self.prompts = PromptLibrary.load(self.config.prompts_dir)
            except PromptError as exc:
                self.prompts = None
                self.motivo_modo_basico = f"prompts indisponíveis: {exc}"
                logger.warning("AcessaCidade Helper sem prompts (%s); usando modo básico", exc)
        self._client: OpenRouterClient | None = None
        # Diagnóstico da última chamada ao LLM (tokens e duração). Informativo e não
        # sincronizado entre threads: usado pelos scripts de exemplo/estimativa de custo.
        self.ultima_chamada_llm: dict[str, Any] | None = None
        if self.config.has_api_key and self.prompts is not None:
            self._client = OpenRouterClient(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                timeout_seconds=self.config.timeout_seconds,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                transport=transport,
            )
        elif not self.config.has_api_key:
            self.motivo_modo_basico = "OPENROUTER_API_KEY não configurada"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "AssistantService":
        return cls(HelperConfig.from_env(env), transport=transport)

    @property
    def llm_enabled(self) -> bool:
        return self._client is not None

    @property
    def modelo(self) -> str | None:
        return self.config.model if self.llm_enabled else None

    # ------------------------------------------------------------------
    def preparar(self, req: AssistantRequest) -> ContextoPreparado:
        avisos: list[str] = []
        mensagem, truncado, pii = preparar_texto_nao_confiavel(req.mensagem, MAX_MENSAGEM)
        if truncado:
            avisos.append(AVISO_TRUNCADO.format(limite=MAX_MENSAGEM))
        if pii:
            avisos.append(AVISO_DADOS_PESSOAIS)

        modo = (req.modo or "geral").strip().lower() if isinstance(req.modo, str) else "geral"
        if modo not in MODOS:
            avisos.append(AVISO_MODO_INVALIDO)
            modo = "geral"

        denuncia = denuncia_segura(req.denuncia)
        protocolo = protocolo_valido(req.protocolo_solicitado)
        if protocolo is None and isinstance(req.protocolo_solicitado, str) and req.protocolo_solicitado.strip():
            # Texto informado não segue o formato: tratamos como não encontrado (sem ecoar lixo).
            protocolo = None
            if denuncia is None:
                avisos.append("O protocolo informado não segue o formato AC-AAAA-NNNNNN.")
        if protocolo is None and denuncia is None:
            protocolo = extract_protocol(mensagem)
        if denuncia is not None:
            proto_denuncia = protocolo_valido(denuncia.get("protocolo"))
            if protocolo and proto_denuncia and protocolo != proto_denuncia:
                # Inconsistência: não arriscar descrever a denúncia errada.
                logger.warning("AcessaCidade Helper: denúncia fornecida não corresponde ao protocolo pedido")
                denuncia = None
            elif proto_denuncia:
                protocolo = proto_denuncia

        tela = req.contexto_tela if isinstance(req.contexto_tela, str) else None
        if tela:
            tela = "".join(ch for ch in tela.lower() if ch.isalnum() or ch in "-_/#")[:40] or None

        return ContextoPreparado(
            mensagem=mensagem,
            modo=modo,
            historico=sanear_historico(req.historico),
            denuncia=denuncia,
            protocolo_solicitado=protocolo,
            indicadores=indicadores_seguros(req.indicadores),
            opcoes=req.opcoes if isinstance(req.opcoes, dict) else None,
            contexto_tela=tela,
            avisos=avisos,
        )

    def build_messages(self, ctx: ContextoPreparado) -> list[dict[str, str]]:
        if self.prompts is None:
            raise PromptError("prompts não carregados")
        system = self.prompts.render_system(
            modo=ctx.modo,
            enumeracoes=texto_enumeracoes(ctx.opcoes),
            significado_status=texto_significado_status(),
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": montar_mensagem_dados(ctx)},
        ]

    # ------------------------------------------------------------------
    def _resposta_fallback(self, ctx: ContextoPreparado, aviso_modo: str) -> AssistantResponse:
        try:
            r = fallback.responder(ctx)
            texto, avisos = r.resposta, r.avisos
        except Exception:  # pragma: no cover - rede de segurança
            logger.exception("AcessaCidade Helper: erro inesperado no modo básico")
            texto, avisos = fallback.resposta_sobre(), []
        return AssistantResponse(
            resposta=texto,
            fonte="fallback",
            modelo=None,
            avisos=_dedup(ctx.avisos + avisos + [aviso_modo]),
            denuncia_referenciada=(ctx.denuncia or {}).get("protocolo") if ctx.denuncia else None,
        )

    def answer(self, req: AssistantRequest) -> AssistantResponse:
        ctx = self.preparar(req)

        if not self.llm_enabled or not ctx.mensagem:
            resp = self._resposta_fallback(ctx, AVISO_MODO_BASICO)
            logger.info("assistente fonte=fallback motivo=%s", "sem_llm" if not self.llm_enabled else "mensagem_vazia")
            return resp

        try:
            messages = self.build_messages(ctx)
            assert self._client is not None
            inicio = time.perf_counter()
            result = self._client.chat(messages)
            self.ultima_chamada_llm = {
                "modelo": result.model,
                "uso": result.usage,
                "duracao_s": round(time.perf_counter() - inicio, 3),
                "finish_reason": result.finish_reason,
            }
        except LLMError as exc:
            logger.warning("assistente fonte=fallback motivo=%s status=%s", exc.code, exc.status_code)
            return self._resposta_fallback(ctx, AVISO_FALHA_LLM.format(motivo=exc.motivo_pt))
        except Exception as exc:  # pragma: no cover - rede de segurança
            logger.warning("assistente fonte=fallback motivo=erro_inesperado tipo=%s", type(exc).__name__)
            return self._resposta_fallback(ctx, AVISO_FALHA_LLM.format(motivo="erro inesperado"))

        texto = limitar_resposta(result.text)
        permitidos = {ctx.protocolo_solicitado} | protocolos_no_texto(ctx.mensagem)
        for h in ctx.historico:
            permitidos |= protocolos_no_texto(h["texto"])
        if ctx.denuncia:
            permitidos.add(ctx.denuncia.get("protocolo"))
        problemas = verificar_resposta_llm(
            texto, protocolos_permitidos={p for p in permitidos if p}, denuncia=ctx.denuncia
        )
        if problemas:
            logger.warning("assistente fonte=fallback motivo=guardrail problemas=%s", ";".join(problemas))
            return self._resposta_fallback(ctx, AVISO_GUARDRAIL.format(motivo=problemas[0]))

        if ctx.protocolo_nao_encontrado and not menciona_nao_encontrado(texto):
            texto = (
                f"Não encontrei nenhuma denúncia com o protocolo {ctx.protocolo_solicitado}.\n\n" + texto
            )

        avisos = list(ctx.avisos)
        avisos.append(AVISO_IA_GERATIVA)
        if ctx.denuncia is not None:
            avisos.append(AVISO_NAO_OFICIAL)
            if ctx.denuncia.get("simulado"):
                avisos.append(AVISO_SIMULADO)
        if ctx.modo == "explicar_resultado" or (ctx.denuncia or {}).get("visao"):
            avisos.append(AVISO_TRIAGEM)

        logger.info("assistente fonte=llm modelo=%s", result.model)
        return AssistantResponse(
            resposta=texto,
            fonte="llm",
            modelo=result.model,
            avisos=_dedup(avisos),
            denuncia_referenciada=ctx.denuncia.get("protocolo") if ctx.denuncia else None,
        )
