"""Tratamento global de erros: mensagens em português, sem stacktrace para o cliente."""
from __future__ import annotations

import json
import logging
from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("acessacidade.erros")

MSG_500 = "Ocorreu um erro interno. Tente novamente em instantes."

MENSAGENS_HTTP = {
    400: "Requisição inválida.",
    401: "Não autorizado.",
    403: "Acesso negado.",
    404: "Recurso não encontrado.",
    405: "Método não permitido para esta rota.",
    413: "O conteúdo enviado é grande demais.",
    415: "Tipo de conteúdo não suportado.",
    429: "Muitas solicitações em pouco tempo. Tente novamente mais tarde.",
    500: MSG_500,
}

_IGNORAR_LOC = {"body", "query", "path", "header", "form", "cookie"}


def _campo(loc) -> str | None:
    for parte in reversed(list(loc or [])):
        if isinstance(parte, str) and parte not in _IGNORAR_LOC:
            return parte
    return None


def traduzir_erro(err: dict) -> str:
    t = err.get("type", "")
    ctx = err.get("ctx") or {}
    if t == "missing":
        return "Campo obrigatório."
    if t == "string_too_short":
        n = ctx.get("min_length", 1)
        return "Não pode ficar em branco." if n == 1 else f"Deve ter pelo menos {n} caracteres."
    if t == "string_too_long":
        return f"Deve ter no máximo {ctx.get('max_length')} caracteres."
    if t == "too_long":
        return f"Itens demais (máximo {ctx.get('max_length')})."
    if t == "too_short":
        return f"Itens de menos (mínimo {ctx.get('min_length')})."
    if t in ("literal_error", "enum"):
        return f"Valor inválido. Opções: {ctx.get('expected', '')}.".replace(" or ", " ou ")
    if t in ("int_parsing", "int_type", "int_from_float"):
        return "Deve ser um número inteiro."
    if t in ("float_parsing", "float_type", "finite_number"):
        return "Deve ser um número."
    if t in ("bool_parsing", "bool_type"):
        return "Deve ser verdadeiro ou falso (true/false)."
    if t == "greater_than_equal":
        return f"Deve ser maior ou igual a {ctx.get('ge')}."
    if t == "greater_than":
        return f"Deve ser maior que {ctx.get('gt')}."
    if t == "less_than_equal":
        return f"Deve ser menor ou igual a {ctx.get('le')}."
    if t == "less_than":
        return f"Deve ser menor que {ctx.get('lt')}."
    if t == "json_invalid":
        return "JSON inválido no corpo da requisição."
    if t in ("model_attributes_type", "dict_type", "model_type"):
        return "O corpo deve ser um objeto JSON."
    if t == "extra_forbidden":
        return "Campo não permitido."
    if t in ("string_type", "str_type"):
        return "Deve ser um texto."
    if t == "list_type":
        return "Deve ser uma lista."
    if t in ("value_error", "assertion_error"):
        msg = str(err.get("msg", ""))
        for prefixo in ("Value error, ", "Assertion failed, "):
            if msg.startswith(prefixo):
                msg = msg[len(prefixo):]
        return msg or "Valor inválido."
    if t in ("upload_file_type", "file_type"):
        return "Envie um arquivo de imagem no campo indicado."
    return "Valor inválido."


async def handler_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    detalhes = []
    for err in exc.errors():
        loc = [p for p in err.get("loc", ()) if isinstance(p, (str, int))]
        detalhes.append({"loc": loc, "campo": _campo(loc), "msg": traduzir_erro(err), "type": err.get("type")})
    return JSONResponse({"detail": detalhes}, status_code=422)


async def handler_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    try:
        padrao = HTTPStatus(exc.status_code).phrase
    except ValueError:
        padrao = None
    if detail is None or detail == padrao or detail == "There was an error parsing the body":
        detail = MENSAGENS_HTTP.get(exc.status_code, "Não foi possível processar a requisição.")
    headers = getattr(exc, "headers", None)
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=headers)


class ErroGlobalMiddleware:
    """Captura exceções não tratadas: 500 com mensagem genérica, sem stacktrace para o cliente."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        iniciou = False

        async def send_wrapper(message: Message) -> None:
            nonlocal iniciou
            if message["type"] == "http.response.start":
                iniciou = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            rota = getattr(scope.get("route"), "path", None)
            logger.error("erro nao tratado", exc_info=True,
                         extra={"evento": "erro_500", "route": rota, "erro": type(exc).__name__})
            if iniciou:
                raise
            corpo = json.dumps({"detail": MSG_500}, ensure_ascii=False).encode("utf-8")
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                    (b"content-length", str(len(corpo)).encode())]})
            await send({"type": "http.response.body", "body": corpo})
