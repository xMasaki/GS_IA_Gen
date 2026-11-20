"""Testes do cliente HTTP do LLM com httpx.MockTransport (sem rede)."""
from __future__ import annotations

import json

import httpx
import pytest

from acessacidade_helper.llm_client import (
    LLMAuthError,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMRequestError,
    LLMServerError,
    LLMTimeoutError,
    OpenRouterClient,
)

CHAVE = "chave-de-teste-ficticia"
BASE = "https://openrouter.ai/api/v1"


def _client(handler, timeout=7.0) -> OpenRouterClient:
    return OpenRouterClient(
        api_key=CHAVE,
        model="openai/gpt-4o-mini",
        base_url=BASE,
        timeout_seconds=timeout,
        transport=httpx.MockTransport(handler),
    )


def _ok(conteudo, model="openai/gpt-4o-mini", **extra):
    corpo = {
        "id": "x",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": conteudo}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }
    corpo.update(extra)
    return httpx.Response(200, json=corpo)


MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def test_sucesso_envia_cabecalhos_e_payload_corretos():
    capturado = {}

    def handler(request: httpx.Request):
        capturado["url"] = str(request.url)
        capturado["headers"] = request.headers
        capturado["body"] = json.loads(request.content)
        capturado["timeout"] = request.extensions.get("timeout")
        return _ok("Resposta de teste.")

    r = _client(handler).chat(MSGS)
    assert r.text == "Resposta de teste."
    assert r.model == "openai/gpt-4o-mini"
    assert r.usage["total_tokens"] == 120
    assert capturado["url"] == f"{BASE}/chat/completions"
    assert capturado["headers"]["authorization"] == f"Bearer {CHAVE}"
    assert capturado["headers"]["x-title"] == "AcessaCidade"
    body = capturado["body"]
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["messages"] == MSGS
    assert body["temperature"] <= 0.3
    assert body["max_tokens"] == 500
    assert body["stream"] is False
    assert capturado["timeout"]["read"] == 7.0


@pytest.mark.parametrize(
    "status,erro",
    [
        (401, LLMAuthError),
        (403, LLMAuthError),
        (402, LLMRateLimitError),
        (429, LLMRateLimitError),
        (500, LLMServerError),
        (502, LLMServerError),
        (503, LLMServerError),
        (400, LLMRequestError),
        (404, LLMRequestError),
    ],
)
def test_status_http_vira_excecao_tipada(status, erro):
    client = _client(lambda r: httpx.Response(status, json={"error": {"message": "x", "code": status}}))
    with pytest.raises(erro) as info:
        client.chat(MSGS)
    assert info.value.status_code == status
    assert CHAVE not in str(info.value)
    assert CHAVE not in repr(info.value)


@pytest.mark.parametrize("exc", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout, httpx.PoolTimeout])
def test_timeout(exc):
    def handler(request):
        raise exc("simulado", request=request)

    with pytest.raises(LLMTimeoutError):
        _client(handler).chat(MSGS)


def test_falha_de_conexao():
    def handler(request):
        raise httpx.ConnectError("sem rede (simulado)", request=request)

    with pytest.raises(LLMConnectionError):
        _client(handler).chat(MSGS)


def test_json_invalido():
    with pytest.raises(LLMInvalidResponseError):
        _client(lambda r: httpx.Response(200, text="<html>erro</html>")).chat(MSGS)


@pytest.mark.parametrize("conteudo", ["", "   \n  ", None])
def test_resposta_vazia(conteudo):
    with pytest.raises(LLMEmptyResponseError):
        _client(lambda r: _ok(conteudo)).chat(MSGS)


@pytest.mark.parametrize(
    "corpo",
    [{"choices": []}, {"choices": "x"}, {"sem": "choices"}, [1, 2, 3], {"choices": [{"message": "texto"}]}],
)
def test_formato_inesperado(corpo):
    with pytest.raises(LLMInvalidResponseError):
        _client(lambda r: httpx.Response(200, json=corpo)).chat(MSGS)


def test_erro_no_corpo_com_status_200():
    corpo = {"error": {"message": "Rate limit", "code": 429}}
    with pytest.raises(LLMRateLimitError):
        _client(lambda r: httpx.Response(200, json=corpo)).chat(MSGS)


def test_conteudo_em_partes_e_modelo_padrao():
    corpo = {"choices": [{"message": {"content": [{"type": "text", "text": "Olá, "}, {"type": "text", "text": "tudo bem."}]}}]}
    r = _client(lambda req: httpx.Response(200, json=corpo)).chat(MSGS)
    assert r.text == "Olá, tudo bem."
    assert r.model == "openai/gpt-4o-mini"  # sem "model" na resposta, usa o configurado


def test_repr_nao_expoe_chave():
    c = _client(lambda r: _ok("x"))
    assert CHAVE not in repr(c)
    assert CHAVE not in str(vars(c).get("model"))


def test_cliente_exige_chave():
    with pytest.raises(ValueError):
        OpenRouterClient(api_key="", model="m", base_url=BASE, timeout_seconds=1)
