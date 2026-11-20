"""Carregamento e renderização dos prompts em ``01-Generative-AI-Engineering/prompts/*.md``.

Marcadores de template (sintaxe ``{{NOME}}``) aceitos no ``system_prompt.md``:

==========================  ==============================================================
``{{INSTRUCOES_DO_MODO}}``  conteúdo de ``modo_geral.md``, ``modo_descricao.md`` ou
                            ``modo_explicar_resultado.md`` (conforme ``AssistantRequest.modo``)
``{{ENUMERACOES}}``         tipos de obstáculo, impactos e classificações da triagem
``{{SIGNIFICADO_STATUS}}``  status com o significado definido no contrato (seção 3.3)
``{{GUIA_PLATAFORMA}}``     conteúdo de ``guia_plataforma.md``
==========================  ==============================================================

Comentários HTML (``<!-- ... -->``) são removidos antes do envio ao modelo — servem para
documentar o arquivo sem gastar tokens. Marcador não substituído gera ``PromptError``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROMPT_FILES: dict[str, str] = {
    "system": "system_prompt.md",
    "geral": "modo_geral.md",
    "descricao": "modo_descricao.md",
    "explicar_resultado": "modo_explicar_resultado.md",
    "guia": "guia_plataforma.md",
}
MARCADORES_SISTEMA = ("INSTRUCOES_DO_MODO", "ENUMERACOES", "SIGNIFICADO_STATUS", "GUIA_PLATAFORMA")

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MARKER_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


class PromptError(RuntimeError):
    """Prompt ausente, vazio ou com marcador não resolvido."""


def strip_comments(texto: str) -> str:
    texto = _COMMENT_RE.sub("", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def render(template: str, valores: dict[str, str]) -> str:
    def _sub(m: re.Match[str]) -> str:
        nome = m.group(1)
        if nome not in valores:
            raise PromptError(f"marcador {{{{{nome}}}}} sem valor")
        return valores[nome]

    resultado = _MARKER_RE.sub(_sub, template)
    return resultado


@dataclass(frozen=True)
class PromptLibrary:
    directory: Path
    templates: dict[str, str]

    @classmethod
    def load(cls, directory: str | Path) -> "PromptLibrary":
        directory = Path(directory)
        if not directory.is_dir():
            raise PromptError(f"pasta de prompts não encontrada: {directory}")
        templates: dict[str, str] = {}
        for nome, arquivo in PROMPT_FILES.items():
            caminho = directory / arquivo
            if not caminho.is_file():
                raise PromptError(f"prompt ausente: {arquivo}")
            conteudo = strip_comments(caminho.read_text(encoding="utf-8-sig"))
            if not conteudo:
                raise PromptError(f"prompt vazio: {arquivo}")
            templates[nome] = conteudo
        faltando = [m for m in MARCADORES_SISTEMA if "{{" + m + "}}" not in templates["system"]]
        if faltando:
            raise PromptError("system_prompt.md sem os marcadores: " + ", ".join(faltando))
        return cls(directory=directory, templates=templates)

    def get(self, nome: str) -> str:
        return self.templates[nome]

    def render_system(self, *, modo: str, enumeracoes: str, significado_status: str) -> str:
        instrucoes = self.templates.get(modo) or self.templates["geral"]
        return render(
            self.templates["system"],
            {
                "INSTRUCOES_DO_MODO": instrucoes,
                "ENUMERACOES": enumeracoes,
                "SIGNIFICADO_STATUS": significado_status,
                "GUIA_PLATAFORMA": self.templates["guia"],
            },
        )
