"""Gera exemplos com o LLM REAL (OpenRouter) usando a chave da própria equipe.

NÃO roda sem ``OPENROUTER_API_KEY``. Nada é inventado: o arquivo salvo contém exatamente o que
o helper devolveu, incluindo casos em que o helper caiu no modo básico (``fonte = fallback``),
que ficam marcados como tal.

Uso (na raiz do repositório, PowerShell):
    # 1) configure a chave no arquivo .env da raiz (nunca versionado) ou na sessão:
    #    $env:OPENROUTER_API_KEY = "<sua chave>"
    .\\.venv\\Scripts\\python.exe 01-Generative-AI-Engineering/examples/gerar_exemplos_llm.py
    .\\.venv\\Scripts\\python.exe 01-Generative-AI-Engineering/examples/gerar_exemplos_llm.py --casos 01_como_registrar 05_consultar_protocolo_inexistente

Saídas: examples/llm_real/respostas_llm_<AAAAMMDD-HHMMSS>.json e .md
Custo: cada caso é uma chamada ao modelo (20 casos no conjunto padrão). Veja README.md, seção de custos.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from _casos import PASTA_EXEMPLOS, RAIZ_REPOSITORIO, bloco_md, carregar_casos, metadados, montar_requisicao, salvar

from acessacidade_helper import AssistantService
from acessacidade_helper.config import load_env_file


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Gera exemplos reais com o LLM configurado.")
    parser.add_argument("--casos", nargs="*", help="ids dos casos (padrão: todos)")
    parser.add_argument("--env-file", default=str(RAIZ_REPOSITORIO / ".env"))
    args = parser.parse_args()

    carregadas = load_env_file(args.env_file)
    if carregadas:
        print(f"variáveis carregadas de {args.env_file}: {', '.join(carregadas)}")

    svc = AssistantService.from_env()
    if not svc.llm_enabled:
        print(
            "ERRO: LLM desabilitado (" + (svc.motivo_modo_basico or "motivo desconhecido") + ").\n"
            "Configure OPENROUTER_API_KEY no .env da raiz ou na sessão e rode novamente.\n"
            "Nenhum arquivo foi gerado (exemplos com LLM real não podem ser inventados).",
            file=sys.stderr,
        )
        return 2

    casos = carregar_casos()
    if args.casos:
        casos = [c for c in casos if c["id"] in set(args.casos)]
    meta = metadados(
        script="gerar_exemplos_llm.py",
        modelo_configurado=svc.config.model,
        base_url=svc.config.base_url,
        temperature=svc.config.temperature,
        max_tokens=svc.config.max_tokens,
    )
    resultados = []
    md = [
        "# Exemplos com LLM real — AcessaCidade Helper",
        "",
        "Gerado por `examples/gerar_exemplos_llm.py` com a chave da equipe. Respostas copiadas",
        "exatamente como o helper devolveu. Denúncias/indicadores de entrada são **dados simulados**.",
        "",
        f"- Gerado em (UTC): `{meta['gerado_em']}`",
        f"- Modelo configurado: `{meta['modelo_configurado']}` — temperature `{meta['temperature']}` — max_tokens `{meta['max_tokens']}`",
        "",
    ]
    total_prompt = total_completion = 0
    for caso in casos:
        svc.ultima_chamada_llm = None
        resp = svc.answer(montar_requisicao(caso)).to_dict()
        diag = svc.ultima_chamada_llm
        uso = (diag or {}).get("uso") or {}
        total_prompt += int(uso.get("prompt_tokens") or 0)
        total_completion += int(uso.get("completion_tokens") or 0)
        resultados.append({"caso": caso, "resposta": resp, "diagnostico_chamada": diag})
        md.append(bloco_md(caso, resp))
        if diag:
            md.append(f"_Diagnóstico: duração {diag.get('duracao_s')} s; uso de tokens {uso or 'não informado'}_\n")
        print(f"{caso['id']}: fonte={resp['fonte']}")

    meta["tokens_prompt_total"] = total_prompt
    meta["tokens_resposta_total"] = total_completion
    meta["respostas_llm"] = sum(1 for r in resultados if r["resposta"]["fonte"] == "llm")
    meta["respostas_fallback"] = sum(1 for r in resultados if r["resposta"]["fonte"] == "fallback")
    md.insert(7, f"- Respostas do LLM: `{meta['respostas_llm']}`; respostas em modo básico (fallback): `{meta['respostas_fallback']}`")
    md.insert(8, f"- Tokens informados pelo provedor: prompt `{total_prompt}`, resposta `{total_completion}`")

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    caminhos = salvar(PASTA_EXEMPLOS / "llm_real", f"respostas_llm_{carimbo}", {"metadados": meta, "resultados": resultados}, "\n".join(md))
    for c in caminhos:
        print(f"salvo: {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
