"""Regras de negócio das denúncias: validação, criação, consulta, listagem e mudança de status."""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from .. import domain as d
from ..config import Settings
from ..db import Database
from ..metrics import Metricas
from ..repository import DenunciaRepository, FiltrosListagem
from .visao import ResultadoTriagem, ServicoVisao

logger = logging.getLogger("acessacidade.denuncias")

MSG_NAO_ENCONTRADA = "Denúncia não encontrada. Confira o protocolo (formato AC-AAAA-NNNNNN) ou o número informado."
MSG_CRIADA = "Denúncia registrada com sucesso. Guarde o protocolo para acompanhar o andamento."
MSG_CRIADA_FOTO = (
    "Denúncia registrada com sucesso. A fotografia passou pela triagem automática e aguarda revisão humana. "
    "Guarde o protocolo para acompanhar o andamento."
)

_VERDADEIROS = {"true", "1", "on", "sim", "yes", "s", "y", "t"}
_FALSOS = {"false", "0", "off", "nao", "não", "no", "n", "f", ""}


def erro_campo(campo: str, msg: str, origem: str = "body") -> dict:
    return {"loc": [origem, campo], "campo": campo, "msg": msg, "type": "value_error"}


def _somar_segundos(iso: str, segundos: int) -> str:
    base = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (base + timedelta(seconds=segundos)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _numero(texto: str | None) -> float | None:
    if texto is None:
        return None
    t = str(texto).strip().replace(",", ".")
    if t == "":
        return None
    try:
        v = float(t)
    except ValueError:
        raise ValueError("não é número") from None
    if not math.isfinite(v):
        raise ValueError("não é finito")
    return v


def validar_entrada(campos: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Valida os campos do formulário (contrato 4.2). Levanta 422 com a lista de erros por campo."""
    erros: list[dict] = []

    def texto(campo: str, minimo: int, maximo: int, obrigatorio: bool, rotulo: str) -> str | None:
        bruto = campos.get(campo)
        valor = (str(bruto) if bruto is not None else "").strip()
        valor = " ".join(valor.split()) if campo != "descricao" else valor
        if not valor:
            if obrigatorio:
                erros.append(erro_campo(campo, f"{rotulo} é obrigatório."))
            return None
        if len(valor) < minimo:
            erros.append(erro_campo(campo, f"{rotulo} deve ter pelo menos {minimo} caracteres."))
        elif len(valor) > maximo:
            erros.append(erro_campo(campo, f"{rotulo} deve ter no máximo {maximo} caracteres."))
        return valor

    nome = texto("nome", 0, 80, False, "O nome")
    logradouro = texto("logradouro", 3, 120, True, "O logradouro")
    numero = texto("numero", 0, 10, False, "O número")
    bairro = texto("bairro", 2, 80, True, "O bairro")
    cidade = texto("cidade", 0, 80, False, "A cidade")
    referencia = texto("ponto_referencia", 0, 150, False, "O ponto de referência")
    descricao = texto("descricao", 10, 1000, True, "A descrição")

    tipo = (campos.get("tipo_obstaculo") or "").strip().upper()
    if not tipo:
        erros.append(erro_campo("tipo_obstaculo", "O tipo de obstáculo é obrigatório."))
    elif tipo not in d.TIPOS_OBSTACULO:
        erros.append(erro_campo("tipo_obstaculo", "Tipo de obstáculo inválido. Opções: " + ", ".join(d.TIPOS_OBSTACULO) + "."))

    impacto = (campos.get("impacto") or "").strip().upper()
    if not impacto:
        erros.append(erro_campo("impacto", "O impacto é obrigatório."))
    elif impacto not in d.IMPACTOS:
        erros.append(erro_campo("impacto", "Impacto inválido. Opções: " + ", ".join(d.IMPACTOS) + "."))

    lat = lon = None
    try:
        lat = _numero(campos.get("latitude"))
    except ValueError:
        erros.append(erro_campo("latitude", "A latitude deve ser um número (ex.: -23.5505)."))
        lat = float("nan")
    try:
        lon = _numero(campos.get("longitude"))
    except ValueError:
        erros.append(erro_campo("longitude", "A longitude deve ser um número (ex.: -46.6333)."))
        lon = float("nan")
    if lat is not None and not math.isnan(lat) and not -90 <= lat <= 90:
        erros.append(erro_campo("latitude", "A latitude deve estar entre -90 e 90."))
    if lon is not None and not math.isnan(lon) and not -180 <= lon <= 180:
        erros.append(erro_campo("longitude", "A longitude deve estar entre -180 e 180."))
    if (lat is None) != (lon is None):
        faltando = "longitude" if lon is None else "latitude"
        erros.append(erro_campo(faltando, "Informe latitude e longitude juntas, ou deixe as duas em branco."))

    consentimento = campos.get("consentimento")
    c = (str(consentimento).strip().lower() if consentimento is not None else None)
    if c is None or c == "":
        erros.append(erro_campo("consentimento", "O consentimento é obrigatório: marque que você concorda com o uso da foto e dos dados."))
    elif c not in _VERDADEIROS:
        if c in _FALSOS:
            erros.append(erro_campo("consentimento", "Para registrar a denúncia é necessário aceitar os termos de uso da foto e dos dados."))
        else:
            erros.append(erro_campo("consentimento", "Valor de consentimento inválido; use true para aceitar."))

    origem = (campos.get("origem") or "WEB").strip().upper() or "WEB"
    if origem not in d.ORIGENS_ENTRADA:
        erros.append(erro_campo("origem", "Origem inválida. Use WEB ou RPA."))

    if erros:
        raise HTTPException(status_code=422, detail=erros)

    return {
        "nome": nome,
        "logradouro": logradouro,
        "numero": numero,
        "bairro": bairro,
        "cidade": cidade or settings.cidade_quando_vazia,
        "ponto_referencia": referencia,
        "tipo_obstaculo": tipo,
        "descricao": descricao,
        "impacto": impacto,
        "latitude": lat,
        "longitude": lon,
        "origem": origem,
        "consentimento": 1,
    }


class ServicoDenuncias:
    def __init__(self, settings: Settings, db: Database, visao: ServicoVisao, metricas: Metricas) -> None:
        self.settings = settings
        self.db = db
        self.repo = DenunciaRepository(db)
        self.visao = visao
        self.metricas = metricas

    # ------------------------------------------------------------ serialização
    def para_publico(self, row: sqlite3.Row, historico: list[sqlite3.Row] | None = None) -> dict[str, Any]:
        visao = None
        if row["visao_json"]:
            try:
                v = json.loads(row["visao_json"])
            except (TypeError, ValueError):
                v = None
            if isinstance(v, dict):
                classif = v.get("classificacao") or row["visao_classificacao"]
                visao = {
                    "classificacao": classif,
                    "rotulo": d.CLASSIFICACOES_VISAO.get(classif, v.get("rotulo") or ""),
                    "pontuacao": float(v.get("pontuacao") or 0.0),
                    "explicacao": list(v.get("explicacao") or []),
                    "metricas": dict(v.get("metricas") or {}),
                    "deteccoes": list(v.get("deteccoes") or []),
                    "imagens": self.visao.urls_etapas(row["id"]) if row["imagem_dir"] else {},
                    "versao_algoritmo": str(v.get("versao_algoritmo") or ""),
                    "aviso": v.get("aviso") or d.AVISO_VISAO,
                }
        obj: dict[str, Any] = {
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
            "tipo_obstaculo_rotulo": d.TIPOS_OBSTACULO.get(row["tipo_obstaculo"], row["tipo_obstaculo"]),
            "descricao": row["descricao"],
            "impacto": row["impacto"],
            "impacto_rotulo": d.IMPACTOS.get(row["impacto"], row["impacto"]),
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "status": row["status"],
            "status_rotulo": d.STATUS.get(row["status"], row["status"]),
            "origem": row["origem"],
            "simulado": bool(row["simulado"]),
            "possui_imagem": bool(row["imagem_dir"]),
            "visao": visao,
            "revisao_humana": row["revisao_humana"],
        }
        if historico is not None:
            obj["historico"] = [
                {
                    "status": h["status"],
                    "status_rotulo": d.STATUS.get(h["status"], h["status"]),
                    "alterado_em": h["alterado_em"],
                    "observacao": h["observacao"],
                }
                for h in historico
            ]
        return obj

    def detalhe_por_id(self, denuncia_id: int) -> dict[str, Any] | None:
        row = self.repo.obter_por_id(denuncia_id)
        if row is None:
            return None
        return self.para_publico(row, self.repo.historico(denuncia_id))

    # ------------------------------------------------------------ consulta
    def obter(self, ref: str) -> dict[str, Any]:
        ref = (ref or "").strip()
        row = None
        if ref.isdigit() and len(ref) <= 12:
            row = self.repo.obter_por_id(int(ref))
        elif d.protocolo_valido(ref):
            row = self.repo.obter_por_protocolo(ref.upper())
        if row is None:
            raise HTTPException(status_code=404, detail=MSG_NAO_ENCONTRADA)
        return self.para_publico(row, self.repo.historico(row["id"]))

    def buscar_por_protocolo(self, protocolo: str) -> dict[str, Any] | None:
        if not d.protocolo_valido(protocolo):
            return None
        row = self.repo.obter_por_protocolo(protocolo.upper())
        return self.para_publico(row, self.repo.historico(row["id"])) if row else None

    def listar(self, filtros: FiltrosListagem, pagina: int, limite: int) -> dict[str, Any]:
        linhas, total = self.repo.listar(filtros, pagina, limite)
        return {"itens": [self.para_publico(r) for r in linhas], "total": total, "pagina": pagina, "limite": limite}

    # ------------------------------------------------------------ criação
    async def criar(self, campos: dict[str, Any], foto: bytes | None) -> dict[str, Any]:
        dados = validar_entrada(campos, self.settings)
        triagem = await run_in_threadpool(self.visao.triar, foto) if foto else None
        detalhe = await run_in_threadpool(self.registrar, dados, triagem)
        detalhe["mensagem"] = MSG_CRIADA_FOTO if triagem else MSG_CRIADA
        return detalhe

    def registrar(self, dados: dict[str, Any], triagem: ResultadoTriagem | None, *,
                  criado_em: str | None = None, simulado: bool = False,
                  status_final: str | None = None, observacao_final: str | None = None) -> dict[str, Any]:
        """Persiste a denúncia + histórico (RECEBIDA → AGUARDANDO_REVISAO se houve triagem)."""
        criado = criado_em or d.agora_iso()
        pasta = self.visao.salvar_etapas(triagem) if triagem else None
        visao = triagem.visao_dict() if triagem else None
        registro = {
            **dados,
            "criado_em": criado,
            "atualizado_em": criado,
            "status": "RECEBIDA",
            "simulado": 1 if simulado else 0,
            "imagem_dir": pasta,
            "visao_json": json.dumps(visao, ensure_ascii=False) if visao else None,
            "visao_classificacao": visao["classificacao"] if visao else None,
            "visao_pontuacao": float(visao["pontuacao"]) if visao else None,
            "revisao_humana": None,
        }
        try:
            with self.db.transacao() as con:
                novo_id, protocolo = self.repo.inserir(con, registro)
                self.repo.inserir_historico(con, novo_id, "RECEBIDA", criado, d.HIST_CRIACAO)
                ultimo = criado
                if triagem:
                    ultimo = criado if criado_em is None else _somar_segundos(criado, 1)
                    self.repo.inserir_historico(con, novo_id, "AGUARDANDO_REVISAO", ultimo, d.HIST_TRIAGEM)
                    self.repo.atualizar_campos(con, novo_id, {"status": "AGUARDANDO_REVISAO", "atualizado_em": ultimo})
                status_atual = "AGUARDANDO_REVISAO" if triagem else "RECEBIDA"
                if status_final and status_final != status_atual:
                    ultimo = _somar_segundos(ultimo, 6 * 3600)
                    self.repo.inserir_historico(con, novo_id, status_final, ultimo, observacao_final)
                    self.repo.atualizar_campos(con, novo_id, {"status": status_final, "atualizado_em": ultimo})
        except Exception:
            self.visao.remover_pasta(pasta)
            raise
        self.metricas.denuncias_criadas_total.labels(dados["origem"], "true" if triagem else "false").inc()
        logger.info(
            "denuncia criada",
            extra={"evento": "denuncia_criada", "protocolo": protocolo, "origem": dados["origem"],
                   "tem_foto": bool(triagem), "classificacao": visao["classificacao"] if visao else None},
        )
        detalhe = self.detalhe_por_id(novo_id)
        assert detalhe is not None
        return detalhe

    # ------------------------------------------------------------ status
    def alterar_status(self, denuncia_id: int, status: str, observacao: str | None,
                       revisao: str | None, revisao_informada: bool) -> dict[str, Any]:
        if status in d.STATUS_EXIGE_OBSERVACAO and not observacao:
            raise HTTPException(
                status_code=422,
                detail=[erro_campo("observacao", f"A observação é obrigatória para o status \"{d.STATUS[status]}\".")],
            )
        row = self.repo.obter_por_id(denuncia_id)
        if row is None:
            raise HTTPException(status_code=404, detail=MSG_NAO_ENCONTRADA)
        quando = d.agora_iso()
        campos: dict[str, Any] = {"status": status, "atualizado_em": quando}
        if revisao_informada:
            campos["revisao_humana"] = revisao
        if not observacao:
            partes = []
            if status != row["status"]:
                partes.append(f"Status alterado para \"{d.STATUS[status]}\" pela equipe")
            if revisao_informada and revisao != row["revisao_humana"]:
                partes.append("Revisão humana: " + (d.REVISOES_HUMANAS.get(revisao, "removida") if revisao else "removida"))
            observacao = "; ".join(partes) or "Registro atualizado pela equipe"
        with self.db.transacao() as con:
            self.repo.atualizar_campos(con, denuncia_id, campos)
            self.repo.inserir_historico(con, denuncia_id, status, quando, observacao)
        logger.info("status alterado", extra={"evento": "status_alterado", "denuncia_id": denuncia_id, "status": status})
        detalhe = self.detalhe_por_id(denuncia_id)
        assert detalhe is not None
        return detalhe
