"""Rotas HTTP da API (contrato, seção 4)."""
from __future__ import annotations

from fastapi import Request

from ..config import Settings


class Servicos:
    """Contêiner simples dos serviços da aplicação (guardado em ``app.state.servicos``)."""

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def servicos(request: Request) -> Servicos:
    return request.app.state.servicos


def settings(request: Request) -> Settings:
    return request.app.state.settings
