"""Testes do AssistantService (interface da seção 6 do contrato) com httpx.MockTransport."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import httpx
import pytest

from acessacidade_helper import (
    AssistantRequest,
    AssistantResponse,
    AssistantService,
    HelperConfig,
    extract_protocol,
)

PASTA = Path(__file__).resolve().parents[1]
PROMPTS = PASTA / "prompts"
ENTRADAS = PASTA / "examples" / "entradas"
CHAVE = "chave-de-teste-ficticia"


def _denuncia(nome="denuncia_simulada_com_foto.json") -> dict:
    return json.loads((ENTRADAS / nome).read_text(encoding="utf-8"))


def _ok(texto, model="openai/gpt-4o-mini"):
    return httpx.Response(
        200,
        json={"model": model, "choices": [{"message": {"role": "assistant", "content": texto}, "finish_reason": "stop"}]},
    )


class Capturador:
    def __init__(self, resposta):
        self.resposta = resposta
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request):
        self.requests.append(json.loads(request.content))
        if callable(self.resposta):
            return self.resposta(request)
        return self.resposta

    @property
    def ultima(self) -> dict:
        return self.requests[-1]


def _svc(handler) -> AssistantService:
    cfg = HelperConfig(api_key=CHAVE, timeout_seconds=2, prompts_dir=PROMPTS)
    return AssistantService(cfg, transport=httpx.MockTransport(handler))


def _sem_chave() -> AssistantService:
    return AssistantService(HelperConfig(api_key="", prompts_dir=PROMPTS))


# ---------------------------------------------------------------- configuração
def test_from_env_sem_chave_fica_em_modo_basico():
    svc = AssistantService.from_env({"OPENROUTER_API_KEY": ""})
    assert svc.llm_enabled is False
    resp = svc.answer(AssistantRequest(mensagem="O que significa aguardando revisão?"))
    assert isinstance(resp, AssistantResponse)
    assert resp.fonte == "fallback"
    assert resp.modelo is None
    assert any("assistente em modo básico" in a.lower() for a in resp.avisos)
    assert "Aguardando revisão" in resp.resposta


def test_from_env_com_chave_habilita_llm_e_le_variaveis():
    env = {
        "OPENROUTER_API_KEY": CHAVE,
        "OPENROUTER_MODEL": "modelo/teste",
        "OPENROUTER_BASE_URL": "https://exemplo.invalid/api/v1/",
        "ASSISTANT_TIMEOUT_SECONDS": "7",
    }
    svc = AssistantService.from_env(env)
    assert svc.llm_enabled is True
    assert svc.config.model == "modelo/teste"
    assert svc.config.base_url == "https://exemplo.invalid/api/v1"
    assert svc.config.timeout_seconds == 7.0
    assert CHAVE not in repr(svc.config)
    assert CHAVE not in str(svc.config)


@pytest.mark.parametrize("valor,esperado", [("abc", 20.0), ("0", 1.0), ("9999", 120.0), ("", 20.0), ("2,5", 2.5)])
def test_timeout_invalido_usa_limites(valor, esperado):
    assert HelperConfig.from_env({"ASSISTANT_TIMEOUT_SECONDS": valor}).timeout_seconds == esperado


def test_base_url_sem_https_volta_ao_padrao():
    assert HelperConfig.from_env({"OPENROUTER_BASE_URL": "http://site.invalid"}).base_url == "https://openrouter.ai/api/v1"


def test_prompts_ausentes_desabilitam_llm_sem_quebrar(tmp_path):
    svc = AssistantService(HelperConfig(api_key=CHAVE, prompts_dir=tmp_path / "nao_existe"))
    assert svc.llm_enabled is False
    assert "prompts" in (svc.motivo_modo_basico or "")
    assert svc.answer(AssistantRequest(mensagem="como registrar?")).fonte == "fallback"


def test_assistant_prompts_dir_sobrescreve(tmp_path):
    destino = tmp_path / "prompts"
    shutil.copytree(PROMPTS, destino)
    sp = destino / "system_prompt.md"
    sp.write_text(sp.read_text(encoding="utf-8") + "\nMARCA-DE-TESTE-OVERRIDE\n", encoding="utf-8")
    cap = Capturador(_ok("Resposta."))
    svc = AssistantService.from_env(
        {"OPENROUTER_API_KEY": CHAVE, "ASSISTANT_PROMPTS_DIR": str(destino)}, transport=httpx.MockTransport(cap)
    )
    assert svc.config.prompts_dir == destino.resolve()
    svc.answer(AssistantRequest(mensagem="oi"))
    assert "MARCA-DE-TESTE-OVERRIDE" in cap.ultima["messages"][0]["content"]


# ---------------------------------------------------------------- LLM: sucesso e falhas
def test_llm_sucesso():
    cap = Capturador(_ok("Para registrar, abra a tela Registrar (#/registrar).", model="openai/gpt-4o-mini-2024"))
    svc = _svc(cap)
    resp = svc.answer(AssistantRequest(mensagem="Como registro um buraco?"))
    assert resp.fonte == "llm"
    assert resp.modelo == "openai/gpt-4o-mini-2024"
    assert resp.resposta.startswith("Para registrar")
    assert any("gerada por IA" in a for a in resp.avisos)
    msgs = cap.ultima["messages"]
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "<mensagem_usuario>\nComo registro um buraco?\n</mensagem_usuario>" in msgs[1]["content"]
    assert svc.ultima_chamada_llm["duracao_s"] >= 0


@pytest.mark.parametrize(
    "handler,motivo",
    [
        (lambda r: httpx.Response(401, json={"error": {"code": 401}}), "chave de API inválida"),
        (lambda r: httpx.Response(429, json={"error": {"code": 429}}), "limite de requisições"),
        (lambda r: httpx.Response(500, text="erro"), "instabilidade"),
        (lambda r: _ok(""), "resposta vazia"),
        (lambda r: httpx.Response(200, text="não é json"), "formato inesperado"),
    ],
)
def test_falhas_da_api_caem_no_fallback_com_aviso(handler, motivo):
    resp = _svc(handler).answer(AssistantRequest(mensagem="O que significa aguardando revisão?"))
    assert resp.fonte == "fallback"
    assert resp.modelo is None
    assert any(motivo in a for a in resp.avisos), resp.avisos
    assert any("modo básico" in a for a in resp.avisos)
    assert "Aguardando revisão" in resp.resposta


def test_timeout_cai_no_fallback():
    def handler(request):
        raise httpx.ReadTimeout("simulado", request=request)

    resp = _svc(handler).answer(AssistantRequest(mensagem="Quais são os status?"))
    assert resp.fonte == "fallback"
    assert any("demorou demais" in a for a in resp.avisos)


def test_chave_nunca_aparece_nos_logs(caplog):
    caplog.set_level(logging.DEBUG)
    _svc(lambda r: httpx.Response(401, json={})).answer(AssistantRequest(mensagem="oi"))
    _svc(lambda r: _ok("ok")).answer(AssistantRequest(mensagem="oi"))
    assert caplog.records  # houve log
    assert CHAVE not in caplog.text


# ---------------------------------------------------------------- guardrails de saída
def test_guardrail_protocolo_inventado_descarta_resposta():
    resp = _svc(lambda r: _ok("Sua denúncia AC-2026-000777 está em análise.")).answer(
        AssistantRequest(mensagem="Como está minha denúncia?")
    )
    assert resp.fonte == "fallback"
    assert any("descartada" in a and "protocolo" in a for a in resp.avisos)
    assert "AC-2026-000777" not in resp.resposta


def test_guardrail_aceita_protocolo_fornecido():
    d = _denuncia()
    texto = "A denúncia AC-2026-000012 está Aguardando revisão. Uma pessoa vai revisar a foto."
    resp = _svc(lambda r: _ok(texto)).answer(
        AssistantRequest(mensagem="Como está minha denúncia?", denuncia=d, protocolo_solicitado="AC-2026-000012")
    )
    assert resp.fonte == "llm"
    assert resp.denuncia_referenciada == "AC-2026-000012"
    assert any("não é um serviço oficial" in a for a in resp.avisos)
    assert any("dados são simulados" in a for a in resp.avisos)


def test_guardrail_status_diferente_dos_dados():
    d = _denuncia()  # status AGUARDANDO_REVISAO
    resp = _svc(lambda r: _ok("Sua denúncia está Resolvida.")).answer(
        AssistantRequest(mensagem="e aí?", denuncia=d, protocolo_solicitado="AC-2026-000012")
    )
    assert resp.fonte == "fallback"
    assert any("status sem base" in a for a in resp.avisos)


def test_guardrail_rota_acessivel():
    resp = _svc(lambda r: _ok("Sim, a rota pela Rua Exemplo é totalmente acessível.")).answer(
        AssistantRequest(mensagem="A rota pela Rua Exemplo é acessível?")
    )
    assert resp.fonte == "fallback"
    assert "Não consigo dizer se um caminho é acessível" in resp.resposta


def test_guardrail_triagem_inventada():
    d = _denuncia("denuncia_simulada_sem_foto.json")
    resp = _svc(lambda r: _ok("A triagem identificou possível buraco na sua foto.")).answer(
        AssistantRequest(mensagem="explique", modo="explicar_resultado", denuncia=d)
    )
    assert resp.fonte == "fallback"
    assert "não tem fotografia" in resp.resposta


# ---------------------------------------------------------------- protocolo
def test_protocolo_nao_encontrado_no_fallback():
    resp = _sem_chave().answer(
        AssistantRequest(mensagem="Qual o status?", protocolo_solicitado="AC-2026-000999", denuncia=None)
    )
    assert resp.fonte == "fallback"
    assert "Não encontrei" in resp.resposta
    assert "AC-2026-000999" in resp.resposta
    assert resp.denuncia_referenciada is None


def test_protocolo_nao_encontrado_no_llm_informa_contexto_e_garante_aviso():
    cap = Capturador(_ok("Confira o número e tente na tela Consultar."))
    resp = _svc(cap).answer(AssistantRequest(mensagem="status?", protocolo_solicitado="AC-2026-000999"))
    assert "NÃO ENCONTRADO" in cap.ultima["messages"][1]["content"]
    assert resp.fonte == "llm"
    assert resp.resposta.startswith("Não encontrei nenhuma denúncia com o protocolo AC-2026-000999")


def test_protocolo_extraido_da_mensagem_quando_nao_informado():
    resp = _sem_chave().answer(AssistantRequest(mensagem="cadê a ac-2026-000321?"))
    assert "AC-2026-000321" in resp.resposta
    assert "Não encontrei" in resp.resposta


def test_denuncia_que_nao_corresponde_ao_protocolo_e_ignorada():
    resp = _sem_chave().answer(
        AssistantRequest(mensagem="status", denuncia=_denuncia(), protocolo_solicitado="AC-2026-000001")
    )
    assert "Não encontrei" in resp.resposta
    assert "Rua Exemplo" not in resp.resposta


def test_extract_protocol_exportado():
    assert extract_protocol("veja AC-2026-000012 por favor") == "AC-2026-000012"
    assert extract_protocol("nada aqui") is None


# ---------------------------------------------------------------- privacidade e limites
def test_dados_sensiveis_nao_vao_ao_llm():
    d = _denuncia()
    d["nome"] = "NOME-QUE-NAO-PODE-SAIR"
    d["latitude"], d["longitude"] = -10.123456, -40.654321
    cap = Capturador(_ok("Ok."))
    _svc(cap).answer(
        AssistantRequest(mensagem="meu telefone é (11) 98765-4321, e-mail fulano@exemplo.com", denuncia=d)
    )
    enviado = json.dumps(cap.ultima, ensure_ascii=False)
    assert "NOME-QUE-NAO-PODE-SAIR" not in enviado
    assert "-10.123456" not in enviado
    assert "98765-4321" not in enviado
    assert "fulano@exemplo.com" not in enviado
    assert "/api/denuncias/12/imagens" not in enviado


def test_mensagem_longa_e_truncada_com_aviso():
    cap = Capturador(_ok("Ok."))
    resp = _svc(cap).answer(AssistantRequest(mensagem="a" * 5000))
    assert any("encurtada" in a for a in resp.avisos)
    conteudo = cap.ultima["messages"][1]["content"]
    assert "a" * 1000 in conteudo and "a" * 1001 not in conteudo


def test_historico_limitado_a_6_itens():
    hist = [{"papel": "usuario" if i % 2 == 0 else "assistente", "texto": f"msg-{i}"} for i in range(10)]
    hist.append({"papel": "system", "texto": "papel inválido"})
    cap = Capturador(_ok("Ok."))
    _svc(cap).answer(AssistantRequest(mensagem="oi", historico=hist))
    conteudo = cap.ultima["messages"][1]["content"]
    assert "msg-3" not in conteudo
    assert all(f"msg-{i}" in conteudo for i in range(5, 10))
    assert "papel inválido" not in conteudo


def test_modo_invalido_vira_geral():
    resp = _sem_chave().answer(AssistantRequest(mensagem="como registrar?", modo="hackear"))
    assert any("Modo desconhecido" in a for a in resp.avisos)


def test_resposta_serializavel_com_campos_do_contrato():
    d = _sem_chave().answer(AssistantRequest(mensagem="oi")).to_dict()
    assert set(d) == {"resposta", "fonte", "modelo", "avisos", "denuncia_referenciada"}
    json.dumps(d)


def test_mensagem_vazia_nao_quebra():
    resp = _svc(lambda r: _ok("x")).answer(AssistantRequest(mensagem="   \x00 "))
    assert resp.fonte == "fallback"
    assert "AcessaCidade Helper" in resp.resposta
