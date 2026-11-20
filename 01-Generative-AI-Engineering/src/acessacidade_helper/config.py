"""Configuração do AcessaCidade Helper a partir de variáveis de ambiente.

Variáveis lidas (ver ``.env.example`` na raiz do repositório):

- ``OPENROUTER_API_KEY``          chave da API (vazia = modo básico por regras)
- ``OPENROUTER_MODEL``            modelo (padrão ``openai/gpt-4o-mini``)
- ``OPENROUTER_BASE_URL``         URL base compatível com OpenAI (padrão ``https://openrouter.ai/api/v1``)
- ``ASSISTANT_TIMEOUT_SECONDS``   tempo limite da chamada (padrão 20 s; limitado a 1..120 s)
- ``ASSISTANT_PROMPTS_DIR``       pasta alternativa de prompts (opcional)

A chave **nunca** aparece em ``repr``, logs ou mensagens de erro.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

logger = logging.getLogger("acessacidade_helper")

DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 20.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 120.0
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 500


def default_prompts_dir() -> Path:
    """``01-Generative-AI-Engineering/prompts`` resolvido a partir deste arquivo.

    config.py -> parents[0]=acessacidade_helper, parents[1]=src, parents[2]=01-Generative-AI-Engineering
    """
    return Path(__file__).resolve().parents[2] / "prompts"


def resolve_prompts_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = (env.get("ASSISTANT_PROMPTS_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return default_prompts_dir()


def _parse_timeout(raw: str | None) -> float:
    if raw is None or not str(raw).strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(str(raw).strip().replace(",", "."))
    except ValueError:
        logger.warning("ASSISTANT_TIMEOUT_SECONDS inválido; usando %.0f s", DEFAULT_TIMEOUT_SECONDS)
        return DEFAULT_TIMEOUT_SECONDS
    if value != value:  # NaN
        return DEFAULT_TIMEOUT_SECONDS
    return max(MIN_TIMEOUT_SECONDS, min(MAX_TIMEOUT_SECONDS, value))


def _valid_base_url(raw: str | None) -> str:
    url = (raw or "").strip().rstrip("/")
    if not url:
        return DEFAULT_BASE_URL
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return url  # útil para testes com um servidor local compatível
    logger.warning("OPENROUTER_BASE_URL inválida (exige https); usando o padrão")
    return DEFAULT_BASE_URL


@dataclass(frozen=True)
class HelperConfig:
    api_key: str = field(default="", repr=False)
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    prompts_dir: Path = field(default_factory=default_prompts_dir)
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def __repr__(self) -> str:  # nunca expõe a chave
        return (
            f"HelperConfig(api_key={'<definida>' if self.api_key else '<vazia>'}, "
            f"model={self.model!r}, base_url={self.base_url!r}, "
            f"timeout_seconds={self.timeout_seconds}, prompts_dir={str(self.prompts_dir)!r})"
        )

    __str__ = __repr__

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "HelperConfig":
        env = os.environ if env is None else env
        key = (env.get("OPENROUTER_API_KEY") or "").strip()
        if any(ch.isspace() for ch in key):
            logger.warning("OPENROUTER_API_KEY contém espaços; ignorada (modo básico)")
            key = ""
        model = (env.get("OPENROUTER_MODEL") or "").strip() or DEFAULT_MODEL
        return cls(
            api_key=key,
            model=model,
            base_url=_valid_base_url(env.get("OPENROUTER_BASE_URL")),
            timeout_seconds=_parse_timeout(env.get("ASSISTANT_TIMEOUT_SECONDS")),
            prompts_dir=resolve_prompts_dir(env),
        )


def load_env_file(path: str | os.PathLike[str], *, override: bool = False) -> list[str]:
    """Carrega um arquivo ``.env`` simples (CHAVE=valor) em ``os.environ``.

    Usado apenas pela CLI e pelos scripts de exemplo (o backend lê o ambiente do processo).
    Não sobrescreve variáveis já definidas (salvo ``override=True``).
    Retorna os NOMES das variáveis carregadas (nunca os valores).
    """
    p = Path(path)
    loaded: list[str] = []
    if not p.is_file():
        return loaded
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not name or not name.replace("_", "").isalnum():
            continue
        if override or name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded
