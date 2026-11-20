"""Gera exemplos REAIS do modo básico (fallback) executando o AcessaCidade Helper.

Uso (na raiz do repositório):
    .\\.venv\\Scripts\\python.exe 01-Generative-AI-Engineering/examples/gerar_exemplos_fallback.py

Saídas: examples/fallback/exemplos_fallback.json e .md (sobrescritos a cada execução).
A chave de API é ignorada de propósito (configuração sem chave) para que todas as respostas
venham do modo por regras — nenhuma chamada de rede é feita.
"""
from __future__ import annotations

from _casos import PASTA_EXEMPLOS, bloco_md, carregar_casos, metadados, montar_requisicao, salvar

from acessacidade_helper import AssistantService, HelperConfig


def main() -> None:
    svc = AssistantService(HelperConfig(api_key=""))
    assert not svc.llm_enabled
    resultados = []
    md = [
        "# Exemplos reais do modo básico (fallback) — AcessaCidade Helper",
        "",
        "Gerado automaticamente por `examples/gerar_exemplos_fallback.py` executando o código do helper",
        "sem chave de API (sem chamadas de rede). Denúncias e indicadores usados são **dados simulados**.",
        "",
    ]
    meta = metadados(script="gerar_exemplos_fallback.py", llm_habilitado=False)
    md.append(f"- Gerado em (UTC): `{meta['gerado_em']}`")
    md.append(f"- Versão do helper: `{meta['versao_helper']}` — Python `{meta['python']}`")
    md.append("")
    for caso in carregar_casos():
        resp = svc.answer(montar_requisicao(caso)).to_dict()
        resultados.append({"caso": caso, "resposta": resp})
        md.append(bloco_md(caso, resp))
    caminhos = salvar(
        PASTA_EXEMPLOS / "fallback",
        "exemplos_fallback",
        {"metadados": meta, "resultados": resultados},
        "\n".join(md),
    )
    for c in caminhos:
        print(f"salvo: {c}")
    print(f"{len(resultados)} casos; fontes: {sorted({r['resposta']['fonte'] for r in resultados})}")


if __name__ == "__main__":
    main()
