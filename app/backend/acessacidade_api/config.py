"""Configuração da API a partir de variáveis de ambiente (ver .env.example na raiz).

Um arquivo ``.env`` na raiz do repositório é carregado manualmente, se existir,
sem dependências extras. Variáveis já definidas no ambiente têm prioridade.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from . import REPO_ROOT, __version__

_VERDADEIROS = {"1", "true", "t", "yes", "y", "sim", "s", "on"}


def parse_dotenv(path: Path) -> dict[str, str]:
    """Lê um arquivo ``KEY=VALOR`` simples (comentários com #, aspas opcionais)."""
    valores: dict[str, str] = {}
    try:
        texto = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return valores
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        if linha.startswith("export "):
            linha = linha[len("export "):]
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        elif " #" in valor:
            valor = valor.split(" #", 1)[0].rstrip()
        if chave:
            valores[chave] = valor
    return valores


def _resolver(caminho: str, padrao: Path) -> Path:
    if not caminho:
        return padrao
    p = Path(caminho).expanduser()
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()


def _bool(valor: str | None, padrao: bool) -> bool:
    if valor is None or valor.strip() == "":
        return padrao
    return valor.strip().lower() in _VERDADEIROS


def _int(valor: str | None, padrao: int, minimo: int = 1) -> int:
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return padrao
    return max(minimo, n)


def _float(valor: str | None, padrao: float, minimo: float = 0.1) -> float:
    try:
        n = float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return padrao
    return max(minimo, n)


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data" / "runtime"
    database_path: Path = REPO_ROOT / "data" / "runtime" / "acessacidade.db"
    max_upload_mb: float = 5.0
    seed_demo_data: bool = True
    cidade_padrao: str = ""
    rate_limit_per_minute: int = 30
    allowed_origins: tuple[str, ...] = ()
    admin_token: str = ""
    pipeline_token: str = ""
    frontend_dir: Path = REPO_ROOT / "app" / "frontend"
    seed_fotos_dir: Path = REPO_ROOT / "data" / "samples" / "fotos"
    versao: str = __version__
    # Ambiente completo repassado ao helper (OPENROUTER_*, ASSISTANT_*).
    env: Mapping[str, str] = field(default_factory=dict, repr=False)

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def gold_snapshot_path(self) -> Path:
        return self.data_dir / "gold_snapshot.json"

    @property
    def cidade_quando_vazia(self) -> str:
        return self.cidade_padrao.strip() or "Não informada"

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None, *, load_dotenv: bool = True,
             dotenv_path: Path | None = None) -> "Settings":
        base: dict[str, str] = {}
        if load_dotenv:
            base.update(parse_dotenv(dotenv_path or (REPO_ROOT / ".env")))
        base.update(dict(os.environ if environ is None else environ))
        g = base.get

        data_dir = _resolver(g("DATA_DIR", ""), REPO_ROOT / "data" / "runtime")
        database_path = _resolver(g("DATABASE_PATH", ""), data_dir / "acessacidade.db")
        origens = tuple(o.strip().rstrip("/") for o in (g("ALLOWED_ORIGINS", "") or "").split(",") if o.strip())
        return cls(
            app_env=(g("APP_ENV", "") or "development").strip(),
            app_port=_int(g("APP_PORT"), 8000),
            log_level=(g("LOG_LEVEL", "") or "INFO").strip().upper(),
            data_dir=data_dir,
            database_path=database_path,
            max_upload_mb=_float(g("MAX_UPLOAD_MB"), 5.0),
            seed_demo_data=_bool(g("SEED_DEMO_DATA"), True),
            cidade_padrao=(g("CIDADE_PADRAO", "") or "").strip()[:80],
            rate_limit_per_minute=_int(g("RATE_LIMIT_PER_MINUTE"), 30),
            allowed_origins=origens,
            admin_token=(g("ADMIN_TOKEN", "") or "").strip(),
            pipeline_token=(g("PIPELINE_TOKEN", "") or "").strip(),
            frontend_dir=_resolver(g("FRONTEND_DIR", ""), REPO_ROOT / "app" / "frontend"),
            seed_fotos_dir=_resolver(g("SEED_FOTOS_DIR", ""), REPO_ROOT / "data" / "samples" / "fotos"),
            env=base,
        )
