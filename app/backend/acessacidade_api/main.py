"""Fábrica da aplicação FastAPI do AcessaCidade.

Execução local (na raiz do repositório)::

    .venv\\Scripts\\python.exe -m uvicorn acessacidade_api.main:app --app-dir app/backend --port 8000
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import Settings
from .db import Database
from .errors import ErroGlobalMiddleware, handler_http, handler_validacao
from .logging_config import configurar_logging
from .metrics import MetricsMiddleware, endpoint_metrics, obter_metricas
from .routes import Servicos
from .routes import assistente as r_assistente
from .routes import denuncias as r_denuncias
from .routes import health as r_health
from .routes import indicadores as r_indicadores
from .routes import meta as r_meta
from .routes import pipeline as r_pipeline
from .routes import visao as r_visao
from .security import EscritaProtegidaMiddleware, RateLimiter, SecurityHeadersMiddleware
from .seed import carregar_seed
from .services.assistente import ServicoAssistente
from .services.denuncias import ServicoDenuncias
from .services.export import ServicoExportacao
from .services.gold import ServicoGold
from .services.indicadores import ServicoIndicadores
from .services.visao import ServicoVisao

logger = logging.getLogger("acessacidade.app")

DESCRICAO_API = (
    "API do **AcessaCidade** — registro, triagem por visão computacional e acompanhamento de denúncias "
    "de problemas de acessibilidade em calçadas e espaços públicos (ODS 11).\n\n"
    "O AcessaCidade **não é serviço oficial do governo**. A triagem automática é apoio e sempre requer "
    "revisão humana. O nome do denunciante nunca é retornado nem exportado."
)


def _docs_html(openapi_url: str) -> HTMLResponse:
    """Swagger UI com uma CSP própria (restrita a /docs) que libera apenas o CDN do Swagger e o script inline exato."""
    pagina = get_swagger_ui_html(openapi_url=openapi_url, title="AcessaCidade API — Documentação")
    html = pagina.body.decode("utf-8")
    hashes = []
    for script in re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL):
        digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode()
        hashes.append(f"'sha256-{digest}'")
    cdn = "https://cdn.jsdelivr.net"
    csp = (
        f"default-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; "
        f"style-src 'self' 'unsafe-inline' {cdn}; script-src 'self' {cdn} {' '.join(hashes)}; "
        f"connect-src 'self'; frame-ancestors 'none'"
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": csp})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    configurar_logging(settings.log_level)
    metricas = obter_metricas()
    db = Database(settings.database_path)

    visao = ServicoVisao(settings, metricas)
    denuncias = ServicoDenuncias(settings, db, visao, metricas)
    indicadores = ServicoIndicadores(denuncias)
    servicos = Servicos(
        visao=visao,
        denuncias=denuncias,
        indicadores=indicadores,
        exportacao=ServicoExportacao(denuncias.repo),
        gold=ServicoGold(settings.gold_snapshot_path),
        assistente=ServicoAssistente(settings, denuncias, indicadores, metricas),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        versao_schema = db.migrar()
        inseridas = 0
        if settings.seed_demo_data:
            inseridas = carregar_seed(denuncias, settings.seed_fotos_dir)
        logger.info(
            "aplicacao iniciada",
            extra={"evento": "inicio", "versao": settings.versao, "ambiente": settings.app_env,
                   "seed": inseridas, "total": versao_schema},
        )
        yield

    app = FastAPI(
        title="AcessaCidade API",
        version=__version__,
        description=DESCRICAO_API,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.metricas = metricas
    app.state.servicos = servicos
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    app.add_exception_handler(RequestValidationError, handler_validacao)
    app.add_exception_handler(StarletteHTTPException, handler_http)

    # ---------------------------------------------------------------- rotas da API
    for modulo in (r_health, r_meta, r_denuncias, r_visao, r_indicadores, r_pipeline, r_assistente):
        app.include_router(modulo.router)
    app.add_api_route("/metrics", endpoint_metrics, methods=["GET"], include_in_schema=False)

    @app.get("/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        return _docs_html(app.openapi_url or "/openapi.json")

    @app.api_route("/api/{caminho:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_nao_encontrada(caminho: str) -> JSONResponse:
        return JSONResponse({"detail": "Rota da API não encontrada. Consulte /docs."}, status_code=404)

    # ---------------------------------------------------------------- frontend estático (APÓS a API)
    if settings.frontend_dir.is_dir() and (settings.frontend_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def raiz() -> dict:
            return {"mensagem": "API do AcessaCidade em execução. Frontend não encontrado; documentação em /docs."}

    # ---------------------------------------------------------------- middlewares (último = mais externo)
    max_corpo_upload = settings.max_upload_bytes + 1024 * 1024  # foto + campos do formulário
    app.add_middleware(
        EscritaProtegidaMiddleware,
        limiter=app.state.rate_limiter,
        rotas={"/api/denuncias": max_corpo_upload, "/api/visao/analisar": max_corpo_upload,
               "/api/assistente": 64 * 1024},
    )
    app.add_middleware(ErroGlobalMiddleware)
    app.add_middleware(MetricsMiddleware, metricas=metricas)
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-Admin-Token", "X-Pipeline-Token"],
            max_age=600,
        )
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def _app_padrao() -> FastAPI:
    return create_app()


app = _app_padrao()
