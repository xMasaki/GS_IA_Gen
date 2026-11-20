"""Saúde, metadados, cabeçalhos de segurança, métricas, erros genéricos e documentação."""
from __future__ import annotations

from acessacidade_api import domain as d

CABECALHOS = {
    "content-security-policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
                               "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=(self)",
}


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["versao"] == "1.0.0"
    assert j["ambiente"] == "test"
    assert j["componentes"] == {"banco": "ok", "visao": "ok", "assistente": "fallback"}


def test_health_degradado_quando_banco_falha(client, monkeypatch):
    monkeypatch.setattr(client.app.state.db, "ping", lambda: False)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degradado"
    assert r.json()["componentes"]["banco"] == "erro"


def test_meta_opcoes(client):
    r = client.get("/api/meta/opcoes")
    assert r.status_code == 200
    j = r.json()
    assert [i["chave"] for i in j["tipo_obstaculo"]] == list(d.TIPOS_OBSTACULO)
    assert {i["chave"]: i["rotulo"] for i in j["impacto"]}["IMPEDE_PASSAGEM"] == "Impede a passagem"
    status = {i["chave"]: i for i in j["status"]}
    assert status["AGUARDANDO_REVISAO"]["rotulo"] == "Aguardando revisão"
    assert "Não representa confirmação de órgão público" in status["RESOLVIDA"]["significado"]
    assert [i["chave"] for i in j["classificacao_visao"]] == ["POSSIBLE_POTHOLE", "NOT_IDENTIFIED", "INCONCLUSIVE"]
    assert [i["chave"] for i in j["origem"]] == ["WEB", "RPA", "SIMULADO", "API"]
    assert j["etapas_imagem"] == ["original", "cinza", "filtrada", "contraste", "bordas", "mascara", "contornos"]
    assert j["max_upload_mb"] == 5.0


def test_cabecalhos_de_seguranca_em_api_estaticos_e_erros(client):
    for caminho in ("/health", "/api/meta/opcoes", "/", "/css/styles.css", "/api/nao-existe", "/arquivo-inexistente.txt"):
        r = client.get(caminho)
        for nome, valor in CABECALHOS.items():
            assert r.headers.get(nome) == valor, (caminho, nome)


def test_raiz_serve_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<html" in r.text.lower()


def test_rota_api_inexistente_404_json_pt(client):
    r = client.get("/api/nao-existe")
    assert r.status_code == 404
    assert "não encontrada" in r.json()["detail"]


def test_docs_e_openapi(client):
    r = client.get("/docs")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "'sha256-" in csp and "unsafe-eval" not in csp
    o = client.get("/openapi.json")
    assert o.status_code == 200
    caminhos = o.json()["paths"]
    for rota in ("/health", "/api/meta/opcoes", "/api/denuncias", "/api/denuncias/{ref}",
                 "/api/denuncias/{id}/imagens/{etapa}", "/api/denuncias/{id}/status", "/api/visao/analisar",
                 "/api/indicadores", "/api/indicadores/analiticos", "/api/pipeline/gold",
                 "/api/export/denuncias", "/api/assistente"):
        assert rota in caminhos, rota


def test_metricas_nomes_e_rota_templated(client, criar):
    assert criar(client).status_code == 201
    client.get("/api/denuncias/1")
    client.get("/api/denuncias/AC-2026-000001")
    r = client.get("/metrics")
    assert r.status_code == 200
    texto = r.text
    for nome in ("acessacidade_http_requests_total", "acessacidade_http_request_duration_seconds",
                 "acessacidade_http_requests_in_progress", "acessacidade_denuncias_criadas_total",
                 "acessacidade_visao_classificacoes_total", "acessacidade_visao_duracao_seconds",
                 "acessacidade_assistente_respostas_total"):
        assert nome in texto, nome
    assert 'route="/api/denuncias/{ref}"' in texto
    assert 'route="/api/denuncias/1"' not in texto
    assert 'route="/api/denuncias/AC-2026-000001"' not in texto
    assert 'acessacidade_denuncias_criadas_total{origem="WEB",tem_foto="false"}' in texto


def test_erro_interno_500_generico_sem_stacktrace(client, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("detalhe interno secreto")

    monkeypatch.setattr(client.app.state.servicos.indicadores, "calcular", explode)
    r = client.get("/api/indicadores")
    assert r.status_code == 500
    assert r.json() == {"detail": "Ocorreu um erro interno. Tente novamente em instantes."}
    assert "secreto" not in r.text and "Traceback" not in r.text
    assert r.headers.get("x-frame-options") == "DENY"


def test_cors_somente_quando_configurado(make_client):
    with make_client() as c:
        r = c.get("/health", headers={"Origin": "https://exemplo.invalid"})
        assert "access-control-allow-origin" not in r.headers
    with make_client(ALLOWED_ORIGINS="https://painel.exemplo.invalid") as c:
        r = c.get("/health", headers={"Origin": "https://painel.exemplo.invalid"})
        assert r.headers.get("access-control-allow-origin") == "https://painel.exemplo.invalid"
