"""Exportação anonimizada para o pipeline de dados (contrato, seção 4.7). Nunca inclui o nome."""
from __future__ import annotations

import csv
import io
from typing import Any

from .. import domain as d
from ..repository import DenunciaRepository

COLUNAS_EXPORTACAO = (
    "id", "protocolo", "criado_em", "atualizado_em", "logradouro", "numero", "bairro", "cidade",
    "ponto_referencia", "tipo_obstaculo", "descricao", "impacto", "latitude", "longitude", "status",
    "origem", "simulado", "possui_imagem", "visao_classificacao", "visao_pontuacao", "revisao_humana",
)


def _linha(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "protocolo": row["protocolo"],
        "criado_em": row["criado_em"],
        "atualizado_em": row["atualizado_em"],
        "logradouro": row["logradouro"],
        "numero": row["numero"],
        "bairro": row["bairro"],
        "cidade": row["cidade"],
        "ponto_referencia": row["ponto_referencia"],
        "tipo_obstaculo": row["tipo_obstaculo"],
        "descricao": row["descricao"],
        "impacto": row["impacto"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "status": row["status"],
        "origem": row["origem"],
        "simulado": bool(row["simulado"]),
        "possui_imagem": bool(row["imagem_dir"]),
        "visao_classificacao": row["visao_classificacao"],
        "visao_pontuacao": row["visao_pontuacao"],
        "revisao_humana": row["revisao_humana"],
    }


class ServicoExportacao:
    def __init__(self, repo: DenunciaRepository) -> None:
        self.repo = repo

    def linhas(self) -> list[dict[str, Any]]:
        return [_linha(r) for r in self.repo.todas(True)]

    def json(self) -> dict[str, Any]:
        return {"colunas": list(COLUNAS_EXPORTACAO), "linhas": self.linhas(), "exportado_em": d.agora_iso()}

    def csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(COLUNAS_EXPORTACAO)
        for linha in self.linhas():
            valores = []
            for c in COLUNAS_EXPORTACAO:
                v = linha[c]
                if isinstance(v, bool):
                    v = "true" if v else "false"
                valores.append("" if v is None else v)
            w.writerow(valores)
        return buf.getvalue()
