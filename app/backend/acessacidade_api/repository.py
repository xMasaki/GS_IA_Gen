"""Acesso a dados (SQL) das denúncias e do histórico de status."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .db import Database
from .domain import ano_de, formatar_protocolo

COLUNAS_INSERCAO = (
    "criado_em", "atualizado_em", "nome", "logradouro", "numero", "bairro", "cidade", "ponto_referencia",
    "tipo_obstaculo", "descricao", "impacto", "latitude", "longitude", "status", "origem", "simulado",
    "consentimento", "imagem_dir", "visao_json", "visao_classificacao", "visao_pontuacao", "revisao_humana",
)


@dataclass
class FiltrosListagem:
    status: str | None = None
    bairro: str | None = None
    tipo_obstaculo: str | None = None
    protocolo: str | None = None
    incluir_simulados: bool = True


class DenunciaRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ----------------------------------------------------------------- escrita
    @staticmethod
    def inserir(con: sqlite3.Connection, dados: dict[str, Any]) -> tuple[int, str]:
        valores = [dados.get(c) for c in COLUNAS_INSERCAO]
        marcadores = ", ".join("?" for _ in COLUNAS_INSERCAO)
        cur = con.execute(
            f"INSERT INTO denuncias ({', '.join(COLUNAS_INSERCAO)}) VALUES ({marcadores})", valores
        )
        novo_id = int(cur.lastrowid)
        protocolo = formatar_protocolo(ano_de(dados["criado_em"]), novo_id)
        con.execute("UPDATE denuncias SET protocolo = ? WHERE id = ?", (protocolo, novo_id))
        return novo_id, protocolo

    @staticmethod
    def inserir_historico(con: sqlite3.Connection, denuncia_id: int, status: str, quando: str,
                          observacao: str | None) -> None:
        con.execute(
            "INSERT INTO historico_status (denuncia_id, status, alterado_em, observacao) VALUES (?, ?, ?, ?)",
            (denuncia_id, status, quando, observacao),
        )

    @staticmethod
    def atualizar_campos(con: sqlite3.Connection, denuncia_id: int, campos: dict[str, Any]) -> None:
        if not campos:
            return
        atribuicoes = ", ".join(f"{c} = ?" for c in campos)
        con.execute(f"UPDATE denuncias SET {atribuicoes} WHERE id = ?", [*campos.values(), denuncia_id])

    # ----------------------------------------------------------------- leitura
    def obter_por_id(self, denuncia_id: int) -> sqlite3.Row | None:
        with self.db.conectar() as con:
            return con.execute("SELECT * FROM denuncias WHERE id = ?", (denuncia_id,)).fetchone()

    def obter_por_protocolo(self, protocolo: str) -> sqlite3.Row | None:
        with self.db.conectar() as con:
            return con.execute("SELECT * FROM denuncias WHERE protocolo = ?", (protocolo.upper(),)).fetchone()

    def historico(self, denuncia_id: int) -> list[sqlite3.Row]:
        with self.db.conectar() as con:
            return con.execute(
                "SELECT status, alterado_em, observacao FROM historico_status WHERE denuncia_id = ? ORDER BY id",
                (denuncia_id,),
            ).fetchall()

    @staticmethod
    def _where(f: FiltrosListagem) -> tuple[str, list[Any]]:
        clausulas: list[str] = []
        params: list[Any] = []
        if f.status:
            clausulas.append("status = ?")
            params.append(f.status)
        if f.tipo_obstaculo:
            clausulas.append("tipo_obstaculo = ?")
            params.append(f.tipo_obstaculo)
        if f.bairro:
            clausulas.append("LOWER(bairro) LIKE ? ESCAPE '\\'")
            termo = f.bairro.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{termo}%")
        if f.protocolo:
            clausulas.append("protocolo = ?")
            params.append(f.protocolo.upper())
        if not f.incluir_simulados:
            clausulas.append("simulado = 0")
        return (" WHERE " + " AND ".join(clausulas)) if clausulas else "", params

    def listar(self, f: FiltrosListagem, pagina: int, limite: int) -> tuple[list[sqlite3.Row], int]:
        where, params = self._where(f)
        with self.db.conectar() as con:
            total = con.execute(f"SELECT COUNT(*) FROM denuncias{where}", params).fetchone()[0]
            linhas = con.execute(
                f"SELECT * FROM denuncias{where} ORDER BY criado_em DESC, id DESC LIMIT ? OFFSET ?",
                [*params, limite, (pagina - 1) * limite],
            ).fetchall()
        return linhas, int(total)

    def todas(self, incluir_simulados: bool = True) -> list[sqlite3.Row]:
        where = "" if incluir_simulados else " WHERE simulado = 0"
        with self.db.conectar() as con:
            return con.execute(f"SELECT * FROM denuncias{where} ORDER BY id").fetchall()

    def contar(self) -> int:
        with self.db.conectar() as con:
            return int(con.execute("SELECT COUNT(*) FROM denuncias").fetchone()[0])
