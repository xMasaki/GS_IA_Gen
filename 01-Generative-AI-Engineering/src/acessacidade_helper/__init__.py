"""AcessaCidade Helper — assistente de IA generativa do AcessaCidade (Disciplina 01).

Interface pública (seção 6 de docs/CONTRATOS_DE_INTEGRACAO.md)::

    from acessacidade_helper import AssistantService, AssistantRequest, AssistantResponse, extract_protocol

    svc = AssistantService.from_env()
    svc.llm_enabled            # True se OPENROUTER_API_KEY estiver configurada e os prompts carregados
    resp = svc.answer(AssistantRequest(mensagem="O que significa aguardando revisão?"))
    resp.resposta, resp.fonte, resp.modelo, resp.avisos, resp.denuncia_referenciada
"""
from .config import HelperConfig
from .guardrails import extract_protocol
from .llm_client import (
    LLMAuthError,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMRequestError,
    LLMServerError,
    LLMTimeoutError,
)
from .prompts import PromptError, PromptLibrary
from .service import AssistantRequest, AssistantResponse, AssistantService

__version__ = "1.0.0"

__all__ = [
    "AssistantService",
    "AssistantRequest",
    "AssistantResponse",
    "extract_protocol",
    "HelperConfig",
    "PromptLibrary",
    "PromptError",
    "LLMError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMServerError",
    "LLMRequestError",
    "LLMTimeoutError",
    "LLMConnectionError",
    "LLMInvalidResponseError",
    "LLMEmptyResponseError",
    "__version__",
]
