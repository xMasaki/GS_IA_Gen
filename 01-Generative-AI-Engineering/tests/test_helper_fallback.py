"""Testes do modo alternativo (regras e intenções em pt-BR)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from acessacidade_helper import AssistantRequest, AssistantService, HelperConfig
from acessacidade_helper.fallback import detectar_intencao, estruturar_descricao

PASTA = Path(__file__).resolve().parents[1]
ENTRADAS = PASTA / "examples" / "entradas"


@pytest.fixture(scope="module")
def svc() -> AssistantService:
    s = AssistantService(HelperConfig(api_key="", prompts_dir=PASTA / "prompts"))
    assert not s.llm_enabled
    return s


def _json(nome):
    return json.loads((ENTRADAS / nome).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mensagem,intencao",
    [
        ("Como faço para registrar um buraco?", "registrar"),
        ("quero denunciar uma calçada quebrada", "registrar"),
        ("O que significa Em análise?", "status"),
        ("o que quer dizer análise inconclusiva", "triagem"),
        ("Quero acompanhar minha denúncia", "protocolo"),
        ("me ajuda a escrever a descrição", "descricao"),
        ("e a LGPD? meu nome aparece?", "privacidade"),
        ("qual a relação com a ODS 11?", "ods"),
        ("quando a prefeitura vai consertar?", "oficial"),
        ("a rota pela praça é acessível?", "rota"),
        ("quantas denúncias tem no painel?", "indicadores"),
        ("meu avô está machucado", "emergencia"),
        ("oi", "saudacao"),
        ("quem é você?", "sobre"),
        ("qual o resultado do jogo de futebol?", "triagem"),  # "resultado" puxa triagem (resposta segura)
        ("me conta uma piada", "fora_escopo"),
    ],
)
def test_detectar_intencao(mensagem, intencao):
    assert detectar_intencao(mensagem) == intencao


def test_como_registrar(svc):
    r = svc.answer(AssistantRequest(mensagem="Como registro um problema na calçada?"))
    assert "#/registrar" in r.resposta and "protocolo" in r.resposta
    assert "consentimento" in r.resposta


def test_status_especifico_e_todos(svc):
    r = svc.answer(AssistantRequest(mensagem="O que significa encaminhada?"))
    assert "Encaminhada" in r.resposta and "encaminhada ao responsável" in r.resposta
    r = svc.answer(AssistantRequest(mensagem="Quais os status?"))
    for rotulo in ("Recebida", "Em análise", "Aguardando revisão", "Encaminhada", "Resolvida"):
        assert rotulo in r.resposta
    assert "Não representa confirmação de órgão público" in r.resposta


def test_explicar_resultado_com_denuncia(svc):
    d = _json("denuncia_simulada_com_foto.json")
    r = svc.answer(AssistantRequest(mensagem="explique", modo="explicar_resultado", denuncia=d))
    assert "Possível buraco identificado" in r.resposta
    assert "0,72" in r.resposta and "não é probabilidade" in r.resposta
    assert "Região escura" in r.resposta  # usa a explicação fornecida
    assert any("Não é avaliação técnica nem oficial" in a for a in r.avisos)
    assert r.denuncia_referenciada == "AC-2026-000012"


def test_explicar_resultado_sem_foto(svc):
    d = _json("denuncia_simulada_sem_foto.json")
    r = svc.answer(AssistantRequest(mensagem="explique", modo="explicar_resultado", denuncia=d))
    assert "não tem fotografia" in r.resposta


def test_explicar_resultado_generico_tres_classes(svc):
    r = svc.answer(AssistantRequest(mensagem="o que é isso?", modo="explicar_resultado"))
    for rotulo in ("Possível buraco identificado", "Nenhum indício suficiente de buraco", "Análise inconclusiva"):
        assert rotulo in r.resposta


def test_explicar_resultado_protocolo_inexistente(svc):
    r = svc.answer(AssistantRequest(mensagem="explique", modo="explicar_resultado", protocolo_solicitado="AC-2026-000404"))
    assert r.resposta.startswith("Não encontrei nenhuma denúncia com o protocolo AC-2026-000404")


def test_consulta_resume_denuncia_fornecida(svc):
    d = _json("denuncia_simulada_sem_foto.json")
    r = svc.answer(AssistantRequest(mensagem="como está?", denuncia=d, protocolo_solicitado="AC-2026-000007"))
    assert "Encontrei a denúncia AC-2026-000007" in r.resposta
    assert "Em análise" in r.resposta and "Avenida Modelo" in r.resposta
    assert "Sem fotografia" in r.resposta
    assert any("dados são simulados" in a for a in r.avisos)
    assert any("não é um serviço oficial" in a for a in r.avisos)


def test_consulta_sem_protocolo_pede_numero(svc):
    r = svc.answer(AssistantRequest(mensagem="quero acompanhar minha denúncia"))
    assert "protocolo" in r.resposta and "AC-AAAA-NNNNNN" in r.resposta


def test_modo_descricao_estrutura_sem_inventar(svc):
    texto = "Tem um buraco de 40 cm na Rua Exemplo, em frente ao mercado. Cadeirantes não conseguem passar."
    r = svc.answer(AssistantRequest(mensagem=texto, modo="descricao"))
    assert "- O quê: Buraco na calçada" in r.resposta
    assert "- Onde: Rua Exemplo" in r.resposta
    assert "- Tamanho aproximado: 40 cm" in r.resposta
    assert "- Impacto: Impede a passagem" in r.resposta
    assert "- Quem é afetado: cadeirantes" in r.resposta
    assert "Sugestão de descrição" in r.resposta
    assert "Para deixar a descrição mais completa" not in r.resposta  # nada faltando


def test_modo_descricao_pergunta_o_que_falta(svc):
    r = svc.answer(AssistantRequest(mensagem="tem um poste no meio da calçada", modo="descricao"))
    assert "[não informado]" in r.resposta
    assert "Onde fica?" in r.resposta
    assert "Qual o tamanho aproximado?" in r.resposta


def test_modo_descricao_texto_curto_pede_informacoes(svc):
    r = svc.answer(AssistantRequest(mensagem="ajuda", modo="descricao"))
    assert "O que é o problema?" in r.resposta


def test_modo_descricao_remove_dado_pessoal(svc):
    r = svc.answer(
        AssistantRequest(mensagem="Rampa quebrada na Rua Exemplo. Meu celular é 11 91234-5678.", modo="descricao")
    )
    assert "91234-5678" not in r.resposta
    assert "removido]" not in r.resposta.split("Sugestão de descrição")[1].split("\n")[1]


def test_estruturar_descricao_buraco_na_via():
    info = estruturar_descricao("buraco enorme no meio da rua na faixa de pedestre, risco de queda para idosos")
    assert info["tipo_obstaculo"] == "BURACO_VIA"
    assert info["impacto"] == "RISCO_QUEDA"
    assert "pessoas idosas" in info["afetados"]
    assert info["tamanho"] == "enorme"


def test_privacidade_ods_rota_oficial_emergencia_fora(svc):
    assert "nunca aparece" in svc.answer(AssistantRequest(mensagem="LGPD e privacidade")).resposta
    assert "11.7" in svc.answer(AssistantRequest(mensagem="ODS?")).resposta
    rota = svc.answer(AssistantRequest(mensagem="Posso passar pela rua tal com cadeira de rodas?")).resposta
    assert "Não consigo dizer se um caminho é acessível" in rota
    assert "não é um serviço oficial" in svc.answer(AssistantRequest(mensagem="qual o prazo da prefeitura?")).resposta
    assert "192" in svc.answer(AssistantRequest(mensagem="socorro, alguém está ferido")).resposta
    fora = svc.answer(AssistantRequest(mensagem="me conta uma piada"))
    assert "não consigo ajudar com esse assunto" in fora.resposta


def test_indicadores_fornecidos_e_ausentes(svc):
    ind = _json("indicadores_simulados.json")
    r = svc.answer(AssistantRequest(mensagem="quantas denúncias existem?", indicadores=ind))
    assert "37" in r.resposta and "dados simulados" in r.resposta
    r = svc.answer(AssistantRequest(mensagem="quantas denúncias existem?"))
    assert "#/painel" in r.resposta and "37" not in r.resposta


def test_fallback_nunca_cita_protocolo_que_nao_recebeu(svc):
    import re

    for msg in ("como registrar?", "quero acompanhar", "status", "o que é triagem?", "privacidade"):
        r = svc.answer(AssistantRequest(mensagem=msg))
        assert not re.search(r"AC-\d{4}-\d{6}", r.resposta), (msg, r.resposta)
