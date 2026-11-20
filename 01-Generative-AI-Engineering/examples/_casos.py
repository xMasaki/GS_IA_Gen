"""Utilidades compartilhadas pelos scripts de geração de exemplos (não é um teste)."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

PASTA_EXEMPLOS = Path(__file__).resolve().parent
PASTA_DISCIPLINA = PASTA_EXEMPLOS.parent
RAIZ_REPOSITORIO = PASTA_DISCIPLINA.parent
PASTA_ENTRADAS = PASTA_EXEMPLOS / "entradas"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

if str(PASTA_DISCIPLINA / "src") not in sys.path:
    sys.path.insert(0, str(PASTA_DISCIPLINA / "src"))

from acessacidade_helper import AssistantRequest, __version__  # noqa: E402


def agora_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ler_json(nome: str | None) -> dict | None:
    if not nome:
        return None
    return json.loads((PASTA_ENTRADAS / nome).read_text(encoding="utf-8"))


def carregar_casos() -> list[dict]:
    dados = json.loads((PASTA_EXEMPLOS / "perguntas_teste.json").read_text(encoding="utf-8"))
    return dados["casos"]


def montar_requisicao(caso: dict) -> AssistantRequest:
    denuncia = ler_json(caso.get("denuncia"))
    protocolo = caso.get("protocolo") or (denuncia or {}).get("protocolo")
    return AssistantRequest(
        mensagem=caso["mensagem"],
        modo=caso.get("modo", "geral"),
        denuncia=denuncia,
        protocolo_solicitado=protocolo,
        indicadores=ler_json(caso.get("indicadores")),
        contexto_tela=caso.get("contexto_tela", "assistente"),
    )


def metadados(**extra) -> dict:
    return {
        "gerado_em": agora_iso(),
        "versao_helper": __version__,
        "python": platform.python_version(),
        **extra,
    }


def salvar(pasta: Path, nome_base: str, dados: dict, markdown: str) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    caminho_json = pasta / f"{nome_base}.json"
    caminho_md = pasta / f"{nome_base}.md"
    caminho_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    caminho_md.write_text(markdown, encoding="utf-8")
    return caminho_json, caminho_md


def bloco_md(caso: dict, resposta: dict) -> str:
    linhas = [f"## {caso['id']} — {caso.get('objetivo', '')}", ""]
    linhas.append(f"- **Modo:** `{caso.get('modo', 'geral')}`")
    if caso.get("protocolo"):
        linhas.append(f"- **Protocolo solicitado:** `{caso['protocolo']}`")
    if caso.get("denuncia"):
        linhas.append(f"- **Denúncia fornecida (simulada):** `entradas/{caso['denuncia']}`")
    if caso.get("indicadores"):
        linhas.append(f"- **Indicadores fornecidos (simulados):** `entradas/{caso['indicadores']}`")
    linhas += ["", "**Mensagem:**", "", "> " + caso["mensagem"], "", "**Resposta** "
               f"(fonte: `{resposta['fonte']}`, modelo: `{resposta.get('modelo')}`):", "", "```text",
               resposta["resposta"], "```", ""]
    if resposta.get("avisos"):
        linhas.append("**Avisos:**")
        linhas += [f"- {a}" for a in resposta["avisos"]]
        linhas.append("")
    return "\n".join(linhas)
