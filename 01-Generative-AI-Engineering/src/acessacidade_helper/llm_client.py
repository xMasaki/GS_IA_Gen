"""Cliente HTTP mínimo para APIs compatíveis com OpenAI ``/chat/completions`` (OpenRouter).

- Usa ``httpx`` (síncrono). Aceita ``transport`` para testes com ``httpx.MockTransport`` (sem rede).
- Cabeçalhos: ``Authorization: Bearer <chave>`` e ``X-Title: AcessaCidade``.
- Erros viram exceções tipadas (``LLMError`` e subclasses) com mensagem em português,
  **sem** a chave e sem o corpo da resposta do provedor.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("acessacidade_helper")

APP_TITLE = "AcessaCidade"


class LLMError(Exception):
    """Falha ao consultar o modelo. ``code`` é estável (usado em avisos e testes)."""

    code = "erro_llm"
    motivo_pt = "erro ao consultar o modelo de IA"

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message or self.motivo_pt)


class LLMAuthError(LLMError):
    code = "autenticacao"
    motivo_pt = "chave de API inválida ou sem permissão"


class LLMRateLimitError(LLMError):
    code = "limite_requisicoes"
    motivo_pt = "limite de requisições ou de créditos atingido"


class LLMServerError(LLMError):
    code = "erro_servidor"
    motivo_pt = "o serviço de IA está com instabilidade"


class LLMRequestError(LLMError):
    code = "requisicao_recusada"
    motivo_pt = "o serviço de IA recusou a requisição"


class LLMTimeoutError(LLMError):
    code = "tempo_esgotado"
    motivo_pt = "o serviço de IA demorou demais para responder"


class LLMConnectionError(LLMError):
    code = "conexao"
    motivo_pt = "não foi possível conectar ao serviço de IA"


class LLMInvalidResponseError(LLMError):
    code = "resposta_invalida"
    motivo_pt = "o serviço de IA devolveu uma resposta em formato inesperado"


class LLMEmptyResponseError(LLMInvalidResponseError):
    code = "resposta_vazia"
    motivo_pt = "o serviço de IA devolveu uma resposta vazia"


@dataclass
class LLMResult:
    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None


def _error_for_status(status: int) -> LLMError:
    if status in (401, 403):
        return LLMAuthError(status_code=status)
    if status == 429 or status == 402:  # 402: créditos insuficientes (OpenRouter)
        return LLMRateLimitError(status_code=status)
    if status >= 500:
        return LLMServerError(status_code=status)
    return LLMRequestError(status_code=status)


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # formato multi-partes
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        temperature: float = 0.2,
        max_tokens: int = 500,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key vazia: o cliente LLM só deve ser criado com chave")
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenRouterClient(model={self.model!r}, base_url={self.base_url!r})"

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": APP_TITLE,
        }

    def build_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        payload = self.build_payload(messages)
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = client.post(self.endpoint, headers=self._headers(), json=payload)
        except httpx.TimeoutException:
            raise LLMTimeoutError() from None
        except httpx.HTTPError as exc:
            raise LLMConnectionError(f"{LLMConnectionError.motivo_pt} ({type(exc).__name__})") from None

        if response.status_code != 200:
            raise _error_for_status(response.status_code)

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            raise LLMInvalidResponseError(status_code=200) from None

        if not isinstance(data, dict):
            raise LLMInvalidResponseError(status_code=200)

        # Alguns provedores devolvem 200 com {"error": {...}}
        if isinstance(data.get("error"), dict):
            err_code = data["error"].get("code")
            if isinstance(err_code, int):
                raise _error_for_status(err_code)
            raise LLMServerError(status_code=200)

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise LLMInvalidResponseError(status_code=200)
        message = choices[0].get("message") or {}
        if not isinstance(message, dict):
            raise LLMInvalidResponseError(status_code=200)
        text = _extract_text(message.get("content")).strip()
        if not text:
            raise LLMEmptyResponseError(status_code=200)

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        model = data.get("model") if isinstance(data.get("model"), str) and data.get("model") else self.model
        return LLMResult(
            text=text,
            model=model,
            usage=usage,
            finish_reason=choices[0].get("finish_reason"),
        )
