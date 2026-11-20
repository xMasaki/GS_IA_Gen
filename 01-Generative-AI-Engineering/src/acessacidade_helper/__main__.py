"""CLI para testes manuais do AcessaCidade Helper (sem backend).

Exemplos (na raiz do repositório, PowerShell):

    $env:PYTHONPATH = "01-Generative-AI-Engineering/src"
    .\\.venv\\Scripts\\python.exe -m acessacidade_helper "O que significa aguardando revisão?"
    .\\.venv\\Scripts\\python.exe -m acessacidade_helper "Como está minha denúncia?" --protocolo AC-2026-000999
    .\\.venv\\Scripts\\python.exe -m acessacidade_helper "explique o resultado" --modo explicar_resultado `
        --denuncia-json 01-Generative-AI-Engineering/examples/entradas/denuncia_simulada_com_foto.json
    .\\.venv\\Scripts\\python.exe -m acessacidade_helper "tem um buraco grande na rua das flores" --modo descricao --json

Sem ``OPENROUTER_API_KEY`` (ou com ``--sem-llm``) a resposta vem do modo básico por regras.
O arquivo ``.env`` da raiz do repositório é lido automaticamente (sem sobrescrever o ambiente);
a chave nunca é exibida.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_env_file
from .service import AssistantRequest, AssistantService

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]


def _ler_json(caminho: str | None, rotulo: str) -> dict | None:
    if not caminho:
        return None
    p = Path(caminho)
    try:
        dados = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"Arquivo de {rotulo} não encontrado: {p}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Arquivo de {rotulo} não é um JSON válido: {exc}")
    if not isinstance(dados, dict):
        raise SystemExit(f"O arquivo de {rotulo} deve conter um objeto JSON.")
    return dados


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="python -m acessacidade_helper",
        description="Pergunte ao AcessaCidade Helper pelo terminal (testes manuais, sem backend).",
    )
    parser.add_argument("pergunta", help="mensagem da pessoa usuária (1 a 1000 caracteres)")
    parser.add_argument("--protocolo", help="protocolo pedido (AC-AAAA-NNNNNN)")
    parser.add_argument("--modo", default="geral", choices=["geral", "descricao", "explicar_resultado"])
    parser.add_argument("--denuncia-json", help="arquivo JSON com o objeto Denuncia público (simula o backend)")
    parser.add_argument("--indicadores-json", help="arquivo JSON com o resumo de /api/indicadores")
    parser.add_argument("--contexto-tela", help="tela de origem (ex.: consulta, registrar)")
    parser.add_argument("--sem-llm", action="store_true", help="força o modo básico, mesmo com chave")
    parser.add_argument("--env-file", default=str(RAIZ_REPOSITORIO / ".env"), help="arquivo .env a carregar")
    parser.add_argument("--json", action="store_true", help="imprime a resposta completa em JSON")
    args = parser.parse_args(argv)

    if args.sem_llm:
        os.environ["OPENROUTER_API_KEY"] = ""
    else:
        carregadas = load_env_file(args.env_file)
        if carregadas:
            print(f"(variáveis carregadas de {args.env_file}: {', '.join(carregadas)})", file=sys.stderr)

    denuncia = _ler_json(args.denuncia_json, "denúncia")
    indicadores = _ler_json(args.indicadores_json, "indicadores")
    protocolo = args.protocolo or (denuncia or {}).get("protocolo")

    svc = AssistantService.from_env()
    req = AssistantRequest(
        mensagem=args.pergunta,
        modo=args.modo,
        denuncia=denuncia,
        protocolo_solicitado=protocolo,
        indicadores=indicadores,
        contexto_tela=args.contexto_tela,
    )
    resp = svc.answer(req)

    if args.json:
        print(json.dumps(resp.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(resp.resposta)
        print()
        print(f"[fonte: {resp.fonte}" + (f" | modelo: {resp.modelo}" if resp.modelo else "") + "]")
        if resp.denuncia_referenciada:
            print(f"[denúncia referenciada: {resp.denuncia_referenciada}]")
        for aviso in resp.avisos:
            print(f"[aviso] {aviso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
