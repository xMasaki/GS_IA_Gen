"""Testes de carregamento e renderização dos prompts."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from acessacidade_helper.config import default_prompts_dir, resolve_prompts_dir
from acessacidade_helper.context import texto_enumeracoes, texto_significado_status
from acessacidade_helper.prompts import PROMPT_FILES, PromptError, PromptLibrary

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def test_caminho_padrao_resolvido_a_partir_do_pacote():
    assert default_prompts_dir() == PROMPTS.resolve()
    assert resolve_prompts_dir({}) == PROMPTS.resolve()


def test_todos_os_prompts_carregam():
    lib = PromptLibrary.load(PROMPTS)
    assert set(lib.templates) == set(PROMPT_FILES)
    for nome, conteudo in lib.templates.items():
        assert conteudo.strip(), nome
        assert "<!--" not in conteudo, f"comentário não removido em {nome}"


@pytest.mark.parametrize("modo", ["geral", "descricao", "explicar_resultado"])
def test_render_substitui_todos_os_marcadores(modo):
    lib = PromptLibrary.load(PROMPTS)
    s = lib.render_system(modo=modo, enumeracoes=texto_enumeracoes(), significado_status=texto_significado_status())
    assert "{{" not in s and "}}" not in s
    assert "AcessaCidade Helper" in s
    assert "Buraco na calçada" in s  # enumerações
    assert "Não representa confirmação de órgão público" in s  # status
    assert "## Telas da plataforma" in s  # guia
    assert lib.get(modo).splitlines()[0] in s  # instruções do modo


def test_prompts_nao_contem_protocolos_de_exemplo():
    import re

    for arquivo in PROMPT_FILES.values():
        texto = (PROMPTS / arquivo).read_text(encoding="utf-8")
        assert not re.search(r"AC-\d{4}-\d{6}", texto), arquivo


def test_prompt_ausente_gera_erro(tmp_path):
    destino = tmp_path / "p"
    shutil.copytree(PROMPTS, destino)
    (destino / "modo_descricao.md").unlink()
    with pytest.raises(PromptError, match="modo_descricao.md"):
        PromptLibrary.load(destino)


def test_marcador_obrigatorio_ausente_gera_erro(tmp_path):
    destino = tmp_path / "p"
    shutil.copytree(PROMPTS, destino)
    sp = destino / "system_prompt.md"
    sp.write_text(sp.read_text(encoding="utf-8").replace("{{GUIA_PLATAFORMA}}", ""), encoding="utf-8")
    with pytest.raises(PromptError, match="GUIA_PLATAFORMA"):
        PromptLibrary.load(destino)


def test_marcador_desconhecido_gera_erro(tmp_path):
    destino = tmp_path / "p"
    shutil.copytree(PROMPTS, destino)
    sp = destino / "system_prompt.md"
    sp.write_text(sp.read_text(encoding="utf-8") + "\n{{MARCADOR_INEXISTENTE}}\n", encoding="utf-8")
    lib = PromptLibrary.load(destino)
    with pytest.raises(PromptError, match="MARCADOR_INEXISTENTE"):
        lib.render_system(modo="geral", enumeracoes="x", significado_status="y")


def test_override_por_variavel(tmp_path):
    assert resolve_prompts_dir({"ASSISTANT_PROMPTS_DIR": str(tmp_path)}) == tmp_path.resolve()


def test_enumeracoes_aceitam_opcoes_do_backend():
    opcoes = {"tipo_obstaculo": [{"chave": "X", "rotulo": "Rótulo X"}], "impacto": {"Y": "Rótulo Y"}}
    t = texto_enumeracoes(opcoes)
    assert "Rótulo X" in t and "Rótulo Y" in t
    assert "Possível buraco identificado" in t
    assert "Buraco na calçada" in texto_enumeracoes({"tipo_obstaculo": "formato inválido"})
