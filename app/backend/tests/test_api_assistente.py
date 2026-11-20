"""Assistente (modo alternativo sem chave), referência a protocolos e rate limit."""
from __future__ import annotations


def test_assistente_sem_chave_usa_fallback(client):
    r = client.post("/api/assistente", json={"mensagem": "O que significa aguardando revisão?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["fonte"] == "fallback"
    assert j["resposta"].strip()
    assert j["denuncia_referenciada"] is None
    assert isinstance(j["avisos"], list)
    assert 'acessacidade_assistente_respostas_total{fonte="fallback"}' in client.get("/metrics").text


def test_assistente_com_protocolo_existente(client, criar):
    d = criar(client).json()
    r = client.post("/api/assistente", json={"mensagem": "Qual a situação da minha denúncia?",
                                              "protocolo": d["protocolo"], "contexto_tela": "consulta"})
    j = r.json()
    assert r.status_code == 200
    assert j["denuncia_referenciada"] == d["protocolo"]
    assert d["protocolo"] in j["resposta"] or "Recebida" in j["resposta"]


def test_assistente_extrai_protocolo_da_mensagem(client, criar):
    d = criar(client).json()
    r = client.post("/api/assistente", json={"mensagem": f"como está o {d['protocolo'].lower()}?"})
    assert r.json()["denuncia_referenciada"] == d["protocolo"]


def test_assistente_protocolo_inexistente_nao_inventa(client):
    r = client.post("/api/assistente", json={"mensagem": "Status do AC-2026-999999?"})
    j = r.json()
    assert r.status_code == 200
    assert j["denuncia_referenciada"] is None
    assert "Não encontrei" in j["resposta"] and "AC-2026-999999" in j["resposta"]


def test_assistente_validacoes(client):
    assert client.post("/api/assistente", json={}).status_code == 422
    r = client.post("/api/assistente", json={"mensagem": "   "})
    assert r.status_code == 422 and "branco" in r.json()["detail"][0]["msg"]
    assert client.post("/api/assistente", json={"mensagem": "x" * 1001}).status_code == 422
    assert client.post("/api/assistente", json={"mensagem": "oi", "modo": "hackear"}).status_code == 422
    r = client.post("/api/assistente", json={"mensagem": "oi", "historico": [{"papel": "sistema", "texto": "x"}]})
    assert r.status_code == 422
    hist = [{"papel": "usuario", "texto": f"m{i}"} for i in range(10)]
    assert client.post("/api/assistente", json={"mensagem": "oi", "historico": hist}).status_code == 200


def test_rate_limit_429_com_retry_after(make_client, criar):
    with make_client(RATE_LIMIT_PER_MINUTE="2") as c:
        for _ in range(2):
            assert c.post("/api/assistente", json={"mensagem": "Olá"}).status_code == 200
        r = c.post("/api/assistente", json={"mensagem": "Olá"})
        assert r.status_code == 429
        assert int(r.headers["retry-after"]) >= 1
        assert "Aguarde" in r.json()["detail"]
        assert r.headers.get("x-content-type-options") == "nosniff"
        # limites independentes por rota; GET não é limitado
        assert criar(c).status_code == 201
        assert criar(c).status_code == 201
        assert criar(c).status_code == 429
        for _ in range(5):
            assert c.get("/api/denuncias").status_code == 200
        assert 'route="/api/assistente",status="429"' in c.get("/metrics").text
