"""Banco operacional SQLite (stdlib): conexão, pragmas e migração idempotente."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .domain import agora_iso

SCHEMA_VERSION = 1

_MIGRACAO_V1 = """
CREATE TABLE IF NOT EXISTS denuncias (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo           TEXT UNIQUE,
    criado_em           TEXT NOT NULL,
    atualizado_em       TEXT NOT NULL,
    nome                TEXT,
    logradouro          TEXT NOT NULL,
    numero              TEXT,
    bairro              TEXT NOT NULL,
    cidade              TEXT NOT NULL,
    ponto_referencia    TEXT,
    tipo_obstaculo      TEXT NOT NULL CHECK (tipo_obstaculo IN ('BURACO_CALCADA','BURACO_VIA','CALCADA_DANIFICADA',
                            'RAMPA_IRREGULAR','PISO_TATIL','OBSTACULO_FIXO','OBSTACULO_TEMPORARIO','OUTRO')),
    descricao           TEXT NOT NULL,
    impacto             TEXT NOT NULL CHECK (impacto IN ('IMPEDE_PASSAGEM','DIFICULTA_PASSAGEM','RISCO_QUEDA','BAIXO_IMPACTO')),
    latitude            REAL,
    longitude           REAL,
    status              TEXT NOT NULL CHECK (status IN ('RECEBIDA','EM_ANALISE','AGUARDANDO_REVISAO','ENCAMINHADA','RESOLVIDA')),
    origem              TEXT NOT NULL CHECK (origem IN ('WEB','RPA','SIMULADO','API')),
    simulado            INTEGER NOT NULL DEFAULT 0 CHECK (simulado IN (0,1)),
    consentimento       INTEGER NOT NULL DEFAULT 1,
    imagem_dir          TEXT,
    visao_json          TEXT,
    visao_classificacao TEXT CHECK (visao_classificacao IS NULL OR visao_classificacao IN ('POSSIBLE_POTHOLE','NOT_IDENTIFIED','INCONCLUSIVE')),
    visao_pontuacao     REAL,
    revisao_humana      TEXT CHECK (revisao_humana IS NULL OR revisao_humana IN ('CONFIRMADO','DESCARTADO'))
);
CREATE TABLE IF NOT EXISTS historico_status (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    denuncia_id  INTEGER NOT NULL REFERENCES denuncias(id) ON DELETE CASCADE,
    status       TEXT NOT NULL,
    alterado_em  TEXT NOT NULL,
    observacao   TEXT
);
CREATE INDEX IF NOT EXISTS idx_denuncias_criado_em ON denuncias(criado_em);
CREATE INDEX IF NOT EXISTS idx_denuncias_status ON denuncias(status);
CREATE INDEX IF NOT EXISTS idx_denuncias_bairro ON denuncias(bairro);
CREATE INDEX IF NOT EXISTS idx_denuncias_tipo ON denuncias(tipo_obstaculo);
CREATE INDEX IF NOT EXISTS idx_denuncias_simulado ON denuncias(simulado);
CREATE INDEX IF NOT EXISTS idx_historico_denuncia ON historico_status(denuncia_id);
"""


class Database:
    """Abre uma conexão curta por operação (seguro entre threads do threadpool)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _abrir(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 10000")
        return con

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        con = self._abrir()
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        con = self._abrir()
        try:
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")
        finally:
            con.close()

    def migrar(self) -> int:
        """Cria tabelas e índices se não existirem (idempotente). Devolve a versão do schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as con:
            con.execute("PRAGMA journal_mode = WAL")
            con.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (versao INTEGER PRIMARY KEY, aplicada_em TEXT NOT NULL)"
            )
            atual = con.execute("SELECT COALESCE(MAX(versao), 0) FROM schema_version").fetchone()[0]
            if atual < 1:
                con.executescript("BEGIN;\n" + _MIGRACAO_V1 + "\nCOMMIT;")
                con.execute(
                    "INSERT OR IGNORE INTO schema_version (versao, aplicada_em) VALUES (?, ?)", (1, agora_iso())
                )
            return max(atual, SCHEMA_VERSION)

    def ping(self) -> bool:
        try:
            with self.conectar() as con:
                return con.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False
