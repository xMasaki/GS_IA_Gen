"""Segurança (contrato, seção 11): cabeçalhos, rate limit em memória, limite de corpo e tokens."""
from __future__ import annotations

import json
import math
import secrets
import threading
import time
from collections import deque

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP_PADRAO = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'"
)

CABECALHOS_SEGURANCA: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(self)"),
)

MSG_DESATIVADA = "Funcionalidade desativada neste ambiente."
MSG_TOKEN_INVALIDO = "Token de acesso ausente ou inválido."


class SecurityHeadersMiddleware:
    """Adiciona os cabeçalhos de segurança em TODAS as respostas (API, estáticos, erros).

    A CSP só é adicionada quando a resposta ainda não definiu uma própria (caso da página
    /docs, que precisa carregar o Swagger UI com uma CSP específica e restrita a ela).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                nomes = {k.lower() for k, _ in headers}
                if b"content-security-policy" not in nomes:
                    headers.append((b"content-security-policy", CSP_PADRAO.encode()))
                for k, v in CABECALHOS_SEGURANCA:
                    if k not in nomes:
                        headers.append((k, v))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RateLimiter:
    """Janela deslizante de 60 s por (chave, IP). Em memória: vale por processo/instância."""

    def __init__(self, limite_por_minuto: int, janela_s: float = 60.0, max_clientes: int = 20000) -> None:
        self.limite = max(1, int(limite_por_minuto))
        self.janela = janela_s
        self.max_clientes = max_clientes
        self._eventos: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def verificar(self, chave: str, ip: str, agora: float | None = None) -> tuple[bool, int]:
        """Registra a tentativa. Devolve (permitido, segundos_para_tentar_novamente)."""
        agora = time.monotonic() if agora is None else agora
        corte = agora - self.janela
        with self._lock:
            if len(self._eventos) > self.max_clientes:
                self._limpar(corte)
            fila = self._eventos.setdefault((chave, ip), deque())
            while fila and fila[0] <= corte:
                fila.popleft()
            if len(fila) >= self.limite:
                espera = max(1, math.ceil(fila[0] + self.janela - agora))
                return False, espera
            fila.append(agora)
            return True, 0

    def _limpar(self, corte: float) -> None:
        for k in [k for k, f in self._eventos.items() if not f or f[-1] <= corte]:
            del self._eventos[k]
        if len(self._eventos) > self.max_clientes:  # proteção contra exaustão de memória
            self._eventos.clear()

    def reiniciar(self) -> None:
        with self._lock:
            self._eventos.clear()


async def _responder_json(send: Send, status: int, detail: str, extras: list[tuple[bytes, bytes]] | None = None) -> None:
    corpo = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    headers = [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(corpo)).encode())]
    headers.extend(extras or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": corpo})


class EscritaProtegidaMiddleware:
    """Rate limit por IP e limite de tamanho do corpo nas rotas de escrita/IA.

    Roda antes da leitura do corpo (multipart/JSON), então um cliente bloqueado não
    consegue forçar o servidor a processar uploads.
    """

    def __init__(self, app: ASGIApp, limiter: RateLimiter, rotas: dict[str, int]) -> None:
        # rotas: caminho -> tamanho máximo do corpo em bytes
        self.app = app
        self.limiter = limiter
        self.rotas = rotas

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        caminho = scope.get("path", "").rstrip("/") or "/"
        limite_corpo = self.rotas.get(caminho)
        if limite_corpo is None:
            await self.app(scope, receive, send)
            return

        scope["acessacidade_route"] = caminho  # rótulo de métrica caso a resposta saia daqui (429/413)
        ip = (scope.get("client") or ("desconhecido", 0))[0] or "desconhecido"
        permitido, espera = self.limiter.verificar(caminho, ip)
        if not permitido:
            await _responder_json(
                send, 429,
                f"Muitas solicitações em pouco tempo. Aguarde {espera} segundo(s) e tente novamente.",
                [(b"retry-after", str(espera).encode())],
            )
            return

        msg_grande = "O conteúdo enviado é grande demais. Reduza o tamanho da fotografia e tente novamente."
        for k, v in scope.get("headers", []):
            if k.lower() == b"content-length":
                try:
                    if int(v) > limite_corpo:
                        await _responder_json(send, 413, msg_grande)
                        return
                except ValueError:
                    pass

        # Corpo sem Content-Length (chunked): conta os bytes durante a leitura.
        estado = {"recebido": 0, "excedeu": False, "iniciou": False}

        async def receive_limitado() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                estado["recebido"] += len(message.get("body", b""))
                if estado["recebido"] > limite_corpo:
                    estado["excedeu"] = True
                    raise CorpoGrandeDemais()
            return message

        async def send_filtrado(message: Message) -> None:
            if estado["excedeu"]:
                return  # descarta a resposta gerada pela aplicação; enviaremos 413
            if message["type"] == "http.response.start":
                estado["iniciou"] = True
            await send(message)

        try:
            await self.app(scope, receive_limitado, send_filtrado)
        except CorpoGrandeDemais:
            estado["excedeu"] = True
        except Exception:
            if not estado["excedeu"]:
                raise
        if estado["excedeu"] and not estado["iniciou"]:
            await _responder_json(send, 413, msg_grande)


class CorpoGrandeDemais(Exception):
    pass


def verificar_token(configurado: str, recebido: str | None) -> None:
    """403 se o token não estiver configurado no servidor; 401 se ausente/incorreto."""
    if not configurado:
        raise HTTPException(status_code=403, detail=MSG_DESATIVADA)
    if not recebido or not secrets.compare_digest(recebido.strip().encode("utf-8"), configurado.encode("utf-8")):
        raise HTTPException(status_code=401, detail=MSG_TOKEN_INVALIDO)
