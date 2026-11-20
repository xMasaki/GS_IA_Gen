"""Métricas Prometheus (contrato, seção 10) e middleware HTTP.

O rótulo ``route`` usa o TEMPLATE da rota (ex.: ``/api/denuncias/{ref}``), nunca o caminho
com IDs, para evitar alta cardinalidade. Requisições que não casam com rota de API
(arquivos estáticos ou 404) são agrupadas em rótulos fixos.
"""
from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class Metricas:
    """Conjunto de métricas. Usa o REGISTRY global por padrão (inclui ``process_*``)."""

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        self.registry = registry
        self.http_requests_total = Counter(
            "acessacidade_http_requests_total", "Total de requisições HTTP",
            ["method", "route", "status"], registry=registry,
        )
        self.http_request_duration_seconds = Histogram(
            "acessacidade_http_request_duration_seconds", "Duração das requisições HTTP em segundos",
            ["method", "route"], registry=registry,
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )
        self.http_requests_in_progress = Gauge(
            "acessacidade_http_requests_in_progress", "Requisições HTTP em andamento", registry=registry,
        )
        self.denuncias_criadas_total = Counter(
            "acessacidade_denuncias_criadas_total", "Denúncias criadas", ["origem", "tem_foto"], registry=registry,
        )
        self.visao_classificacoes_total = Counter(
            "acessacidade_visao_classificacoes_total", "Classificações da triagem por visão computacional",
            ["classificacao"], registry=registry,
        )
        self.visao_duracao_seconds = Histogram(
            "acessacidade_visao_duracao_seconds", "Duração da triagem de imagem (validação+sanitização+análise)",
            registry=registry, buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
        )
        self.assistente_respostas_total = Counter(
            "acessacidade_assistente_respostas_total", "Respostas do AcessaCidade Helper", ["fonte"],
            registry=registry,
        )

    def exposicao(self) -> Response:
        return Response(generate_latest(self.registry), media_type=CONTENT_TYPE_LATEST)


_METRICAS_GLOBAIS: Metricas | None = None


def obter_metricas() -> Metricas:
    """Métricas são registradas uma única vez por processo (várias create_app() reutilizam)."""
    global _METRICAS_GLOBAIS
    if _METRICAS_GLOBAIS is None:
        _METRICAS_GLOBAIS = Metricas()
    return _METRICAS_GLOBAIS


def _rotulo_rota(scope: Scope) -> str:
    rota = scope.get("route")
    caminho = getattr(rota, "path", None)
    if caminho:
        return caminho if caminho != "" else "/"
    if scope.get("acessacidade_route"):
        return scope["acessacidade_route"]
    path = scope.get("path", "")
    if path.startswith("/api/"):
        return "/api/{nao_encontrada}"
    return "/{estatico}"


class MetricsMiddleware:
    """Middleware ASGI puro (não interfere em streaming/FileResponse)."""

    def __init__(self, app: ASGIApp, metricas: Metricas) -> None:
        self.app = app
        self.m = metricas

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        metodo = scope.get("method", "GET")
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
            await send(message)

        inicio = time.perf_counter()
        self.m.http_requests_in_progress.inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self.m.http_requests_in_progress.dec()
            rota = _rotulo_rota(scope)
            self.m.http_request_duration_seconds.labels(metodo, rota).observe(time.perf_counter() - inicio)
            self.m.http_requests_total.labels(metodo, rota, str(status_holder["status"])).inc()


async def endpoint_metrics(request: Request) -> Response:
    return request.app.state.metricas.exposicao()
