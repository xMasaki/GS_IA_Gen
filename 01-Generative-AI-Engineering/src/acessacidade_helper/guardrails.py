"""Guardrails do AcessaCidade Helper.

Entrada:
- limites de tamanho (mensagem e histórico — seção 4.9 do contrato);
- remoção de caracteres de controle e normalização Unicode;
- remoção de dados pessoais óbvios (e-mail, CPF, telefone) antes de enviar ao LLM;
- neutralização dos delimitadores usados no prompt (defesa contra *prompt injection*:
  texto do usuário e da denúncia é sempre DADO dentro de blocos delimitados).

Saída (verificação pós-resposta do LLM):
- protocolo ``AC-AAAA-NNNNNN`` citado que não foi fornecido → descarta;
- afirmação de status de denúncia sem dados (ou diferente dos dados) → descarta;
- afirmação de resultado de triagem diferente dos dados → descarta;
- afirmação de que rota/calçada/local é acessível ou seguro → descarta.

As verificações de saída são heurísticas (expressões regulares sobre texto normalizado);
os limites estão documentados em docs/RISCOS_E_LIMITES.md.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from .domain import PROTOCOLO_BUSCA_REGEX, PROTOCOLO_REGEX, STATUS

MAX_MENSAGEM = 1000
MAX_HISTORICO_ITENS = 6
MAX_HISTORICO_TEXTO = 1000
MAX_CAMPO_DENUNCIA = 1000
MAX_RESPOSTA = 2000

# Nomes dos blocos delimitados usados na mensagem enviada ao LLM (ver context.py)
DELIMITADORES = (
    "contexto_sistema",
    "dados_denuncia",
    "dados_indicadores",
    "historico_conversa",
    "mensagem_usuario",
)
_DELIM_RE = re.compile(
    r"<\s*/?\s*(?:" + "|".join(DELIMITADORES) + r")\s*/?\s*>",
    re.IGNORECASE,
)

# Caracteres de controle (C0/C1) exceto \n e \t, e caracteres invisíveis de formatação
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁠-⁤﻿]")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CPF_RE = re.compile(r"(?<![\w-])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\w-])")
_TELEFONE_RE = re.compile(
    r"(?<![\w-])(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[-\s]?\d{4}(?![\w-])"
)

# ---------------------------------------------------------------------------
# Avisos padronizados (texto exibido ao cidadão)
# ---------------------------------------------------------------------------
AVISO_MODO_BASICO = (
    "Assistente em modo básico: as respostas são geradas por regras pré-definidas, "
    "sem modelo de IA."
)
AVISO_FALHA_LLM = (
    "Não foi possível consultar o modelo de IA agora ({motivo}). "
    "Assistente em modo básico: resposta gerada por regras pré-definidas."
)
AVISO_GUARDRAIL = (
    "A resposta do modelo de IA foi descartada porque não passou na verificação de "
    "segurança ({motivo}). Assistente em modo básico: resposta gerada por regras pré-definidas."
)
AVISO_TRIAGEM = (
    "A triagem automática da foto é só um apoio inicial. Não é avaliação técnica nem "
    "oficial e precisa de revisão humana."
)
AVISO_NAO_OFICIAL = (
    "O AcessaCidade não é um serviço oficial do governo. O status mostra o registro da "
    "equipe do AcessaCidade, não uma confirmação de órgão público."
)
AVISO_DADOS_PESSOAIS = (
    "Retiramos da mensagem algo que parece dado pessoal (telefone, e-mail ou CPF). "
    "Você não precisa informar esses dados."
)
AVISO_TRUNCADO = "Sua mensagem era longa e foi encurtada para {limite} caracteres."
AVISO_SIMULADO = "Esta denúncia é de demonstração: os dados são simulados."
AVISO_MODO_INVALIDO = "Modo desconhecido; usado o modo geral."
AVISO_IA_GERATIVA = (
    "Resposta gerada por IA. Pode conter erros: confira as informações na própria plataforma."
)


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos — usado só para comparar/buscar padrões."""
    nfkd = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return sem_acento.lower()


def remover_controles(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto or "")
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_RE.sub("", texto)


def limpar_texto(texto: Any, limite: int) -> tuple[str, bool]:
    """Remove controles, colapsa espaços/linhas em excesso e limita o tamanho.

    Retorna ``(texto_limpo, foi_truncado)``.
    """
    if texto is None:
        return "", False
    if not isinstance(texto, str):
        texto = str(texto)
    texto = remover_controles(texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) > limite:
        return texto[:limite].rstrip(), True
    return texto, False


def neutralizar_delimitadores(texto: str) -> str:
    """Impede que dados não confiáveis abram/fechem os blocos delimitados do prompt."""
    return _DELIM_RE.sub("[marcador removido]", texto or "")


def remover_dados_pessoais(texto: str) -> tuple[str, list[str]]:
    """Substitui e-mail, CPF e telefone por marcadores. Retorna (texto, tipos_encontrados)."""
    encontrados: list[str] = []
    if _EMAIL_RE.search(texto):
        encontrados.append("email")
        texto = _EMAIL_RE.sub("[e-mail removido]", texto)
    if _CPF_RE.search(texto):
        encontrados.append("cpf")
        texto = _CPF_RE.sub("[CPF removido]", texto)
    if _TELEFONE_RE.search(texto):
        encontrados.append("telefone")
        texto = _TELEFONE_RE.sub("[telefone removido]", texto)
    return texto, encontrados


def preparar_texto_nao_confiavel(texto: Any, limite: int) -> tuple[str, bool, list[str]]:
    """Pipeline completo para qualquer texto vindo do usuário/denúncia."""
    limpo, truncado = limpar_texto(texto, limite)
    limpo = neutralizar_delimitadores(limpo)
    limpo, pii = remover_dados_pessoais(limpo)
    return limpo, truncado, pii


def extract_protocol(texto: str | None) -> str | None:
    """Primeiro protocolo ``AC-AAAA-NNNNNN`` encontrado no texto (normalizado em maiúsculas)."""
    if not texto or not isinstance(texto, str):
        return None
    m = PROTOCOLO_BUSCA_REGEX.search(texto)
    return m.group(0).upper() if m else None


def protocolos_no_texto(texto: str | None) -> set[str]:
    if not texto:
        return set()
    return {m.group(0).upper() for m in PROTOCOLO_BUSCA_REGEX.finditer(texto)}


def protocolo_valido(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    valor = valor.strip().upper()
    return valor if PROTOCOLO_REGEX.match(valor) else None


# ---------------------------------------------------------------------------
# Verificação pós-resposta
# ---------------------------------------------------------------------------
_STATUS_NORMALIZADO = {normalizar(rotulo): chave for chave, rotulo in STATUS.items()}
_STATUS_ALT = "|".join(re.escape(r) for r in sorted(_STATUS_NORMALIZADO, key=len, reverse=True))

_STATUS_CLAIM_RE = re.compile(
    r"(?:\b(?:sua|esta|essa|a|tua)\s+(?:denuncia|ocorrencia|solicitacao)\b|\bac-\d{4}-\d{6}\b)"
    r"[^.!?\n]{0,60}?\b(?:esta|foi|encontra-se|se encontra|consta como|aparece como|ficou)\s+"
    r"(?:como\s+|com\s+(?:o\s+)?status\s+)?[\"'“”«]?(" + _STATUS_ALT + r")\b"
)

_TRIAGEM_CLAIM_RE = re.compile(
    r"\b(?:triagem|analise|foto|imagem|algoritmo)\b[^.!?\n]{0,60}?"
    r"\b(?:identificou|indicou|detectou|classificou|apontou|encontrou|concluiu|resultado foi)\b"
    r"[^.!?\n]{0,40}?(possivel buraco|nenhum indicio|nao identific|inconclusiv)"
)
_TRIAGEM_MAP = {
    "possivel buraco": "POSSIBLE_POTHOLE",
    "nenhum indicio": "NOT_IDENTIFIED",
    "nao identific": "NOT_IDENTIFIED",
    "inconclusiv": "INCONCLUSIVE",
}

_ROTA_RE = re.compile(
    r"\b(?:rota|caminho|trajeto|percurso|calcada|passeio|trecho|local|rua|via)\b"
    r"[^.!?\n]{0,60}?\b(?:e|esta|sera|seria|ficou|eh)\s+"
    r"(?:totalmente\s+|completamente\s+|100%\s+|bem\s+|muito\s+)?(?:acessivel|segur[oa])\b"
)
_PASSAR_RE = re.compile(
    r"\b(?:pode|podera|consegue|conseguira|da para|dá para)\s+passar\b[^.!?\n]{0,30}?"
    r"\b(?:com seguranca|sem problemas|tranquil|sem risco)"
)
# Negação ou condicional na mesma frase ("não posso garantir que...", "se a rota...",
# "quando a denúncia está Resolvida...") desarma a regra.
_NEGACAO_RE = re.compile(r"\b(?:nao|nunca|nem|se|caso|quando|impossivel|incapaz)\b")


def _negado(texto_norm: str, inicio: int, trecho: str) -> bool:
    janela = texto_norm[max(0, inicio - 60):inicio]
    corte = max(janela.rfind("."), janela.rfind("!"), janela.rfind("?"), janela.rfind("\n"))
    if corte >= 0:
        janela = janela[corte + 1:]
    return bool(_NEGACAO_RE.search(janela + " " + trecho))


def _status_permitidos(denuncia: dict | None) -> set[str]:
    if not denuncia:
        return set()
    permitidos = set()
    if isinstance(denuncia.get("status"), str):
        permitidos.add(denuncia["status"])
    for item in denuncia.get("historico") or []:
        if isinstance(item, dict) and isinstance(item.get("status"), str):
            permitidos.add(item["status"])
    return permitidos


def verificar_resposta_llm(
    texto: str,
    *,
    protocolos_permitidos: Iterable[str],
    denuncia: dict | None,
) -> list[str]:
    """Retorna a lista de problemas encontrados (vazia = resposta aprovada)."""
    problemas: list[str] = []
    permitidos = {p.upper() for p in protocolos_permitidos if p}

    citados = protocolos_no_texto(texto)
    estranhos = sorted(citados - permitidos)
    if estranhos:
        problemas.append("citou protocolo não fornecido")

    n = normalizar(texto)

    status_ok = _status_permitidos(denuncia)
    for m in _STATUS_CLAIM_RE.finditer(n):
        if _negado(n, m.start(), m.group(0).replace("se encontra", "encontra")):
            continue
        chave = _STATUS_NORMALIZADO.get(m.group(1))
        if not denuncia or chave not in status_ok:
            problemas.append("afirmou status sem base nos dados")
            break

    visao = (denuncia or {}).get("visao") if isinstance(denuncia, dict) else None
    classe_real = visao.get("classificacao") if isinstance(visao, dict) else None
    for m in _TRIAGEM_CLAIM_RE.finditer(n):
        if _negado(n, m.start(), m.group(0)):
            continue
        frag = m.group(1)
        classe = next((v for k, v in _TRIAGEM_MAP.items() if frag.startswith(k)), None)
        if classe_real is None or classe != classe_real:
            problemas.append("afirmou resultado de triagem sem base nos dados")
            break

    for regex in (_ROTA_RE, _PASSAR_RE):
        for m in regex.finditer(n):
            trecho_sem_verbo = m.group(0)
            if _negado(n, m.start(), trecho_sem_verbo):
                continue
            problemas.append("afirmou que um local é acessível ou seguro")
            break
        if problemas and problemas[-1].startswith("afirmou que um local"):
            break

    return problemas


def menciona_nao_encontrado(texto: str) -> bool:
    n = normalizar(texto)
    return any(
        frase in n
        for frase in ("nao encontr", "nao foi encontrad", "nao localiz", "nao foi localizad", "nao existe")
    )


def limitar_resposta(texto: str, limite: int = MAX_RESPOSTA) -> str:
    texto, _ = limpar_texto(texto, 10 * limite)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    ponto = max(corte.rfind(". "), corte.rfind("\n"))
    if ponto > limite // 2:
        corte = corte[: ponto + 1]
    return corte.rstrip() + " (…)"
