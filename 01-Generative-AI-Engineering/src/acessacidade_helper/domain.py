"""Constantes de domínio do AcessaCidade (espelho da seção 3 de docs/CONTRATOS_DE_INTEGRACAO.md).

O helper usa estas tabelas como padrão quando o backend não envia ``opcoes``.
"""
from __future__ import annotations

import re

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
    "AGUARDANDO_REVISAO": (
        "A triagem automática da foto terminou e uma pessoa precisa revisar o resultado."
    ),
    "ENCAMINHADA": "A equipe registrou que a ocorrência foi encaminhada ao responsável.",
    "RESOLVIDA": (
        "A equipe registrou a ocorrência como resolvida. "
        "Não representa confirmação de órgão público."
    ),
}

CLASSIFICACOES_VISAO: dict[str, str] = {
    "POSSIBLE_POTHOLE": "Possível buraco identificado",
    "NOT_IDENTIFIED": "Nenhum indício suficiente de buraco",
    "INCONCLUSIVE": "Análise inconclusiva",
}
ROTULO_SEM_FOTO = "Sem fotografia (não analisada)"

ORIGENS: dict[str, str] = {
    "WEB": "Formulário web",
    "RPA": "Robô de automação (UiPath)",
    "SIMULADO": "Dado simulado de demonstração",
    "API": "Chamada direta à API",
}

REVISAO_HUMANA: dict[str | None, str] = {
    None: "Ainda não revisada por uma pessoa da equipe",
    "CONFIRMADO": "Uma pessoa da equipe confirmou o problema na foto",
    "DESCARTADO": "Uma pessoa da equipe descartou o resultado da triagem",
}

MODOS = ("geral", "descricao", "explicar_resultado")

# Seção 3.7 do contrato: AC-{ANO}-{ID com 6 dígitos}
PROTOCOLO_REGEX = re.compile(r"^AC-\d{4}-\d{6}$")
PROTOCOLO_BUSCA_REGEX = re.compile(r"(?<![A-Za-z0-9])AC-\d{4}-\d{6}(?![0-9])", re.IGNORECASE)

# Rotas da SPA (seção 7 do contrato)
TELAS: dict[str, str] = {
    "#/": "Início",
    "#/registrar": "Registrar denúncia",
    "#/denuncia/{protocolo}": "Detalhe da denúncia",
    "#/analise": "Testar a triagem de uma foto",
    "#/consultar": "Consultar denúncias",
    "#/assistente": "AcessaCidade Helper",
    "#/painel": "Painel de indicadores",
    "#/revisao": "Área da equipe",
    "#/sobre": "Sobre e privacidade",
}
