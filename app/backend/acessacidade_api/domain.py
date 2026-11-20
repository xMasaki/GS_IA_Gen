"""Domínio: enumerações com rótulos (contrato, seção 3) e utilitários de protocolo/datas."""
from __future__ import annotations

import re
from datetime import datetime, timezone

TIPOS_OBSTACULO: dict[str, str] = {
    "BURACO_CALCADA": "Buraco na calçada",
    "BURACO_VIA": "Buraco na via ou travessia",
    "CALCADA_DANIFICADA": "Calçada quebrada ou desnivelada",
    "RAMPA_IRREGULAR": "Rampa ausente ou irregular",
    "PISO_TATIL": "Piso tátil ausente ou danificado",
    "OBSTACULO_FIXO": "Obstáculo fixo (poste, lixeira, placa)",
    "OBSTACULO_TEMPORARIO": "Obstáculo temporário (entulho, veículo, obra)",
    "OUTRO": "Outro",
}

IMPACTOS: dict[str, str] = {
    "IMPEDE_PASSAGEM": "Impede a passagem",
    "DIFICULTA_PASSAGEM": "Dificulta a passagem",
    "RISCO_QUEDA": "Risco de queda ou acidente",
    "BAIXO_IMPACTO": "Baixo impacto",
}

STATUS: dict[str, str] = {
    "RECEBIDA": "Recebida",
    "EM_ANALISE": "Em análise",
    "AGUARDANDO_REVISAO": "Aguardando revisão",
    "ENCAMINHADA": "Encaminhada",
    "RESOLVIDA": "Resolvida",
}

STATUS_SIGNIFICADO: dict[str, str] = {
    "RECEBIDA": "A denúncia foi registrada no AcessaCidade.",
    "EM_ANALISE": "A equipe do AcessaCidade está verificando as informações.",
    "AGUARDANDO_REVISAO": "A triagem automática da foto terminou e uma pessoa precisa revisar o resultado.",
    "ENCAMINHADA": "A equipe registrou que a ocorrência foi encaminhada ao responsável.",
    "RESOLVIDA": "A equipe registrou a ocorrência como resolvida. Não representa confirmação de órgão público.",
}

CLASSIFICACOES_VISAO: dict[str, str] = {
    "POSSIBLE_POTHOLE": "Possível buraco identificado",
    "NOT_IDENTIFIED": "Nenhum indício suficiente de buraco",
    "INCONCLUSIVE": "Análise inconclusiva",
}
SEM_IMAGEM = "SEM_IMAGEM"
ROTULO_SEM_FOTO = "Sem fotografia (não analisada)"

ORIGENS: dict[str, str] = {"WEB": "WEB", "RPA": "RPA", "SIMULADO": "SIMULADO", "API": "API"}
ORIGENS_DESCRICAO: dict[str, str] = {
    "WEB": "Formulário web",
    "RPA": "Robô UiPath",
    "SIMULADO": "Dados de demonstração (simulados)",
    "API": "Chamada direta à API",
}
ORIGENS_ENTRADA = ("WEB", "RPA")  # aceitas no POST /api/denuncias

REVISOES_HUMANAS: dict[str, str] = {
    "CONFIRMADO": "Pessoa confirmou o problema na foto",
    "DESCARTADO": "Pessoa descartou o resultado da triagem",
}

STATUS_EXIGE_OBSERVACAO = frozenset({"ENCAMINHADA", "RESOLVIDA"})
STATUS_SEED_PERMITIDOS = frozenset({"RECEBIDA", "EM_ANALISE", "AGUARDANDO_REVISAO"})

HIST_CRIACAO = "Denúncia registrada"
HIST_TRIAGEM = "Triagem automática da fotografia concluída; aguardando revisão humana"

AVISO_VISAO = "Triagem automática inicial. Não substitui avaliação técnica; requer revisão humana."

PROTOCOLO_REGEX = re.compile(r"^AC-\d{4}-\d{6}$")


def formatar_protocolo(ano: int, id_: int) -> str:
    return f"AC-{int(ano):04d}-{int(id_):06d}"


def protocolo_valido(texto: str | None) -> bool:
    return bool(texto) and bool(PROTOCOLO_REGEX.match(texto.strip().upper()))


def agora_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def ano_de(iso: str) -> int:
    try:
        return int(iso[:4])
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).year


def lista_opcoes(mapa: dict[str, str], significados: dict[str, str] | None = None) -> list[dict]:
    itens = []
    for chave, rotulo in mapa.items():
        item = {"chave": chave, "rotulo": rotulo}
        if significados and chave in significados:
            item["significado"] = significados[chave]
        itens.append(item)
    return itens


def opcoes(max_upload_mb: float, etapas: tuple[str, ...]) -> dict:
    """Corpo de GET /api/meta/opcoes."""
    return {
        "tipo_obstaculo": lista_opcoes(TIPOS_OBSTACULO),
        "impacto": lista_opcoes(IMPACTOS),
        "status": lista_opcoes(STATUS, STATUS_SIGNIFICADO),
        "classificacao_visao": lista_opcoes(CLASSIFICACOES_VISAO),
        "origem": lista_opcoes(ORIGENS, ORIGENS_DESCRICAO),
        "revisao_humana": lista_opcoes(REVISOES_HUMANAS),
        "etapas_imagem": list(etapas),
        "max_upload_mb": max_upload_mb,
        "formatos_foto": ["image/jpeg", "image/png", "image/webp"],
        "aviso_triagem": AVISO_VISAO,
    }
