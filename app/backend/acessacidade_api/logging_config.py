"""Logging estruturado em JSON lines. Nunca registra nome, chaves de API nem conteúdo de fotos."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# Campos extras aceitos nos logs (lista branca: evita vazar dados pessoais por engano).
CAMPOS_PERMITIDOS = {
    "evento", "protocolo", "origem", "tem_foto", "classificacao", "codigo", "denuncia_id", "status",
    "fonte", "modo", "com_protocolo", "method", "route", "status_code", "duracao_ms", "erro", "total",
    "versao", "ambiente", "seed",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for campo in CAMPOS_PERMITIDOS:
            if campo in record.__dict__:
                dados[campo] = record.__dict__[campo]
        if record.exc_info:
            tipo = record.exc_info[0]
            dados["excecao"] = tipo.__name__ if tipo else None
        return json.dumps(dados, ensure_ascii=False, default=str)


def configurar_logging(nivel: str = "INFO") -> None:
    raiz = logging.getLogger("acessacidade")
    if not any(getattr(h, "_acessacidade", False) for h in raiz.handlers):
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        h._acessacidade = True  # type: ignore[attr-defined]
        raiz.addHandler(h)
    raiz.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    raiz.propagate = False
