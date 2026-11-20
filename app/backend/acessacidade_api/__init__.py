"""AcessaCidade — API FastAPI (backend do MVP).

Ao ser importado, garante que os pacotes das disciplinas usados pelo backend
(``acessacidade_helper`` e ``acessacidade_vision``) estejam importáveis,
inserindo suas pastas ``src`` no ``sys.path`` quando necessário
(contrato de integração, seção 2.1).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

__version__ = "1.0.0"

# app/backend/acessacidade_api/__init__.py -> parents[3] = raiz do repositório
REPO_ROOT = Path(__file__).resolve().parents[3]

_PACOTES_EXTERNOS = {
    "acessacidade_helper": REPO_ROOT / "01-Generative-AI-Engineering" / "src",
    "acessacidade_vision": REPO_ROOT / "04-Applied-Computer-Vision" / "src",
}


def _bootstrap_sys_path() -> None:
    for pacote, pasta in _PACOTES_EXTERNOS.items():
        try:
            encontrado = importlib.util.find_spec(pacote) is not None
        except (ImportError, ValueError):
            encontrado = False
        if not encontrado and pasta.is_dir() and str(pasta) not in sys.path:
            sys.path.insert(0, str(pasta))


_bootstrap_sys_path()
