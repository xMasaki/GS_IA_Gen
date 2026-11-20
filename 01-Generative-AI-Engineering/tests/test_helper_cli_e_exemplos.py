"""Testes da CLI (python -m acessacidade_helper) e da consistência dos exemplos gerados."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from acessacidade_helper import AssistantRequest, AssistantService, HelperConfig

PASTA = Path(__file__).resolve().parents[1]
EXEMPLOS = PASTA / "examples"


def _cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PASTA / "src")
    env["OPENROUTER_API_KEY"] = ""
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "acessacidade_helper", *args, "--env-file", str(PASTA / "nao-existe.env")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )


def test_cli_json_sem_chave():
    p = _cli("O que significa aguardando revisão?", "--json")
    assert p.returncode == 0, p.stderr
    dados = json.loads(p.stdout)
    assert dados["fonte"] == "fallback"
    assert "Aguardando revisão" in dados["resposta"]


def test_cli_protocolo_inexistente():
    p = _cli("Como está minha denúncia?", "--protocolo", "AC-2026-000999")
    assert p.returncode == 0, p.stderr
    assert "Não encontrei nenhuma denúncia com o protocolo AC-2026-000999" in p.stdout
    assert "[fonte: fallback]" in p.stdout


def test_cli_com_denuncia_json():
    p = _cli(
        "explique o resultado", "--modo", "explicar_resultado",
        "--denuncia-json", str(EXEMPLOS / "entradas" / "denuncia_simulada_com_foto.json"), "--json",
    )
    assert p.returncode == 0, p.stderr
    dados = json.loads(p.stdout)
    assert dados["denuncia_referenciada"] == "AC-2026-000012"
    assert "Possível buraco identificado" in dados["resposta"]


def test_cli_arquivo_inexistente_da_erro_claro():
    p = _cli("oi", "--denuncia-json", str(PASTA / "nao-existe.json"))
    assert p.returncode != 0
    assert "não encontrado" in (p.stderr + p.stdout)


def _carregar(caminho: Path) -> dict:
    if not caminho.is_file():
        pytest.skip(f"exemplo ainda não gerado: {caminho.name}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_exemplos_fallback_sao_saidas_reais_do_codigo_atual():
    """As respostas salvas devem ser exatamente o que o código atual produz (regenerar se mudar)."""
    sys.path.insert(0, str(EXEMPLOS))
    try:
        import _casos  # type: ignore
    finally:
        sys.path.pop(0)
    dados = _carregar(EXEMPLOS / "fallback" / "exemplos_fallback.json")
    assert dados["metadados"]["gerado_em"]
    svc = AssistantService(HelperConfig(api_key=""))
    for item in dados["resultados"]:
        atual = svc.answer(_casos.montar_requisicao(item["caso"])).to_dict()
        assert atual == item["resposta"], f"exemplo desatualizado: {item['caso']['id']} — rode gerar_exemplos_fallback.py"


def test_exemplos_de_erro_registrados():
    dados = _carregar(EXEMPLOS / "erros" / "exemplos_erros.json")
    ids = {r["id"] for r in dados["resultados"]}
    assert {"E01_sem_chave", "E02_chave_invalida_401", "E05_timeout", "E08_protocolo_inexistente"} <= ids
    for r in dados["resultados"]:
        assert r["resposta_do_helper"]["fonte"] == "fallback"
        if r["erro_do_cliente_llm"] and r["erro_do_cliente_llm"].get("excecao"):
            assert r["erro_do_cliente_llm"]["chave_aparece_na_mensagem"] is False


def test_nenhum_exemplo_llm_inventado():
    """A pasta llm_real só pode ter respostas geradas pelo script (com metadados e fonte registrada)."""
    for arq in (EXEMPLOS / "llm_real").glob("respostas_llm_*.json"):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        assert dados["metadados"]["script"] == "gerar_exemplos_llm.py"
        for r in dados["resultados"]:
            assert r["resposta"]["fonte"] in {"llm", "fallback"}
