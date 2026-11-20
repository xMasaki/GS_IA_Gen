"""Snapshot Gold publicado pelo pipeline (contrato, seção 4.8), salvo atomicamente em DATA_DIR."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

MSG_INDISPONIVEL = (
    "Ainda não há indicadores analíticos publicados pelo pipeline de dados. "
    "Execute o pipeline (camadas Raw → Bronze → Silver → Gold) para gerar o snapshot."
)


class ServicoGold:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)

    @staticmethod
    def validar(corpo: Any) -> dict[str, Any]:
        if not isinstance(corpo, dict):
            raise HTTPException(status_code=422, detail="O corpo deve ser um objeto JSON.")
        gerado = corpo.get("gerado_em")
        if not isinstance(gerado, str) or not gerado.strip():
            raise HTTPException(status_code=422, detail="O campo \"gerado_em\" é obrigatório no snapshot Gold.")
        return corpo

    def salvar(self, corpo: dict[str, Any]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".gold_", suffix=".tmp", dir=str(self.caminho.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(corpo, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.caminho)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def carregar(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"disponivel": False, "mensagem": MSG_INDISPONIVEL}
        except (OSError, ValueError):
            return {"disponivel": False, "mensagem": "O snapshot analítico salvo está ilegível. Publique-o novamente."}
        if not isinstance(dados, dict):
            return {"disponivel": False, "mensagem": MSG_INDISPONIVEL}
        return {**dados, "disponivel": True}
