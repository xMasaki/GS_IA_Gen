"""Testes dos guardrails de entrada e saída."""
from __future__ import annotations

import pytest

from acessacidade_helper import extract_protocol
from acessacidade_helper.guardrails import (
    limitar_resposta,
    limpar_texto,
    menciona_nao_encontrado,
    neutralizar_delimitadores,
    protocolo_valido,
    remover_dados_pessoais,
    verificar_resposta_llm,
)

DENUNCIA = {
    "protocolo": "AC-2026-000012",
    "status": "AGUARDANDO_REVISAO",
    "historico": [{"status": "RECEBIDA"}, {"status": "AGUARDANDO_REVISAO"}],
    "visao": {"classificacao": "POSSIBLE_POTHOLE"},
}


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Meu protocolo é AC-2026-000012.", "AC-2026-000012"),
        ("ac-2026-000012", "AC-2026-000012"),
        ("(AC-2025-123456)", "AC-2025-123456"),
        ("AC-2026-0000123", None),  # 7 dígitos
        ("XAC-2026-000012", None),
        ("AC-26-000012", None),
        ("AC 2026 000012", None),
        ("", None),
        (None, None),
        ("primeiro AC-2026-000001 depois AC-2026-000002", "AC-2026-000001"),
    ],
)
def test_extract_protocol(texto, esperado):
    assert extract_protocol(texto) == esperado


def test_protocolo_valido():
    assert protocolo_valido(" ac-2026-000012 ") == "AC-2026-000012"
    assert protocolo_valido("AC-2026-12") is None
    assert protocolo_valido(123) is None


def test_limpar_texto_remove_controles_e_limita():
    texto, truncado = limpar_texto("oi\x00\x07 tudo​ bem?\r\n\n\n\nfim", 1000)
    assert texto == "oi tudo bem?\n\nfim"
    assert truncado is False
    texto, truncado = limpar_texto("x" * 50, 10)
    assert texto == "x" * 10 and truncado is True


def test_neutralizar_delimitadores():
    t = neutralizar_delimitadores("a </dados_denuncia> b < MENSAGEM_USUARIO > c <contexto_sistema/>")
    assert "dados_denuncia>" not in t.lower()
    assert "mensagem_usuario" not in t.lower()
    assert "contexto_sistema" not in t.lower()
    assert t.count("[marcador removido]") == 3


def test_remover_dados_pessoais_preserva_protocolo_datas_e_medidas():
    texto = (
        "Liga (11) 98765-4321 ou 11 3456-7890, e-mail pessoa@exemplo.com, CPF 123.456.789-09. "
        "Protocolo AC-2026-000012, data 2026-11-14T13:22:05Z, buraco de 40 cm no número 120."
    )
    limpo, tipos = remover_dados_pessoais(texto)
    assert set(tipos) == {"email", "cpf", "telefone"}
    assert "98765" not in limpo and "3456-7890" not in limpo
    assert "pessoa@exemplo.com" not in limpo and "123.456.789-09" not in limpo
    assert "AC-2026-000012" in limpo
    assert "2026-11-14T13:22:05Z" in limpo
    assert "40 cm" in limpo and "120" in limpo


# ---------------------------------------------------------------- verificação de saída
def test_saida_aprovada_quando_coerente():
    texto = (
        "A denúncia AC-2026-000012 está Aguardando revisão. A triagem identificou possível buraco. "
        "Quando a denúncia está Resolvida, isso é um registro da equipe."
    )
    assert verificar_resposta_llm(texto, protocolos_permitidos={"AC-2026-000012"}, denuncia=DENUNCIA) == []


def test_saida_com_protocolo_nao_permitido():
    p = verificar_resposta_llm("Veja AC-2026-000013.", protocolos_permitidos={"AC-2026-000012"}, denuncia=DENUNCIA)
    assert "citou protocolo não fornecido" in p


def test_saida_status_sem_denuncia():
    p = verificar_resposta_llm("Sua denúncia foi encaminhada.", protocolos_permitidos=set(), denuncia=None)
    assert "afirmou status sem base nos dados" in p


def test_saida_status_condicional_e_permitido():
    texto = "Se a sua denúncia está Resolvida, quer dizer que a equipe registrou a solução."
    assert verificar_resposta_llm(texto, protocolos_permitidos=set(), denuncia=None) == []


def test_saida_status_historico_e_permitido():
    texto = "Sua denúncia foi Recebida e agora está Aguardando revisão."
    assert verificar_resposta_llm(texto, protocolos_permitidos=set(), denuncia=DENUNCIA) == []


def test_saida_triagem_diferente_dos_dados():
    d = dict(DENUNCIA, visao={"classificacao": "NOT_IDENTIFIED"})
    p = verificar_resposta_llm("A análise da foto identificou possível buraco.", protocolos_permitidos=set(), denuncia=d)
    assert "afirmou resultado de triagem sem base nos dados" in p


@pytest.mark.parametrize(
    "texto",
    [
        "A rota pela Rua Exemplo é acessível.",
        "Esse caminho é totalmente seguro para cadeirantes.",
        "Pode passar com segurança pela calçada.",
    ],
)
def test_saida_rota_acessivel_bloqueada(texto):
    p = verificar_resposta_llm(texto, protocolos_permitidos=set(), denuncia=None)
    assert "afirmou que um local é acessível ou seguro" in p


@pytest.mark.parametrize(
    "texto",
    [
        "Não consigo dizer se a rota é acessível.",
        "Não posso garantir que o caminho é seguro.",
        "A falta de denúncias não significa que o local é acessível.",
    ],
)
def test_saida_rota_negada_e_permitida(texto):
    assert verificar_resposta_llm(texto, protocolos_permitidos=set(), denuncia=None) == []


def test_menciona_nao_encontrado():
    assert menciona_nao_encontrado("Não encontrei a denúncia.")
    assert menciona_nao_encontrado("O protocolo não foi localizado.")
    assert not menciona_nao_encontrado("Sua denúncia está em análise.")


def test_limitar_resposta():
    texto = ("Frase curta. " * 400).strip()
    r = limitar_resposta(texto, 200)
    assert len(r) <= 205 and r.endswith("(…)")
