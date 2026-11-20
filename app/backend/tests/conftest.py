"""Fixtures dos testes da API: cada teste usa um DATA_DIR temporário e a fábrica create_app()."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acessacidade_api import REPO_ROOT
from acessacidade_api.config import Settings
from acessacidade_api.main import create_app

FOTOS = REPO_ROOT / "data" / "samples" / "fotos"
FOTO_BURACO = FOTOS / "sintetica_buraco_01.jpg"

ENV_BASE = {
    "APP_ENV": "test",
    "SEED_DEMO_DATA": "false",
    "ADMIN_TOKEN": "",
    "PIPELINE_TOKEN": "",
    "OPENROUTER_API_KEY": "",
    "RATE_LIMIT_PER_MINUTE": "1000",
    "MAX_UPLOAD_MB": "5",
    "ALLOWED_ORIGINS": "",
    "CIDADE_PADRAO": "",
    "DATABASE_PATH": "",
    "LOG_LEVEL": "WARNING",
}

FORM_VALIDO = {
    "nome": "Apelido Teste",
    "logradouro": "Rua Exemplo",
    "numero": "120",
    "bairro": "Centro",
    "cidade": "Cidade Exemplo",
    "ponto_referencia": "Em frente ao ponto de ônibus",
    "tipo_obstaculo": "BURACO_CALCADA",
    "descricao": "Buraco de aproximadamente 40 cm na calçada (teste automatizado).",
    "impacto": "IMPEDE_PASSAGEM",
    "consentimento": "true",
}


@pytest.fixture
def make_client(tmp_path: Path, monkeypatch):
    """Fábrica: ``with make_client(ADMIN_TOKEN="x") as c: ...``."""

    @contextmanager
    def _factory(data_dir: Path | None = None, **env):
        front = tmp_path / "frontend"
        if not front.exists():  # frontend mínimo para os testes não dependerem do outro componente
            (front / "css").mkdir(parents=True)
            (front / "index.html").write_text(
                "<!doctype html><html lang=\"pt-BR\"><head><title>AcessaCidade</title></head><body>ok</body></html>",
                encoding="utf-8")
            (front / "css" / "styles.css").write_text("body{margin:0}", encoding="utf-8")
        valores = {**ENV_BASE, "DATA_DIR": str(data_dir or (tmp_path / "runtime")), "FRONTEND_DIR": str(front), **env}
        for k, v in valores.items():
            monkeypatch.setenv(k, str(v))
        settings = Settings.load(load_dotenv=False)
        app = create_app(settings)
        with TestClient(app) as client:
            client.app_settings = settings  # type: ignore[attr-defined]
            yield client

    return _factory


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c


def criar(client: TestClient, foto: Path | bytes | None = None, nome_arquivo: str = "foto.jpg", **campos):
    dados = {**FORM_VALIDO, **campos}
    dados = {k: v for k, v in dados.items() if v is not None}
    files = None
    if foto is not None:
        conteudo = foto.read_bytes() if isinstance(foto, Path) else foto
        files = {"foto": (nome_arquivo, conteudo, "image/jpeg")}
    return client.post("/api/denuncias", data=dados, files=files)


@pytest.fixture(name="criar")
def fixture_criar():
    """Expõe o helper ``criar(client, foto=None, **campos)`` aos testes."""
    return criar


@pytest.fixture
def form_valido():
    return dict(FORM_VALIDO)
