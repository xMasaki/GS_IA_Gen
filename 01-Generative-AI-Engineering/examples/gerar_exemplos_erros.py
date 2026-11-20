"""Gera exemplos REAIS de tratamento de erros do AcessaCidade Helper.

Os erros da API são SIMULADOS com ``httpx.MockTransport`` (nenhuma chamada de rede é feita e
nenhuma chave real é usada). O código do helper é executado de verdade: as respostas, avisos e
exceções registrados são exatamente o que o helper produziu.

Uso (na raiz do repositório):
    .\\.venv\\Scripts\\python.exe 01-Generative-AI-Engineering/examples/gerar_exemplos_erros.py

Saídas: examples/erros/exemplos_erros.json e .md
"""
from __future__ import annotations

import json

import httpx
from _casos import PASTA_EXEMPLOS, metadados, salvar

from acessacidade_helper import AssistantRequest, AssistantService, HelperConfig, LLMError
from acessacidade_helper.llm_client import OpenRouterClient

CHAVE_FICTICIA = "chave-invalida-simulada-para-teste"  # não é uma credencial
PERGUNTA = "O que significa aguardando revisão?"


def _resposta_ok(texto: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "simulado",
            "model": "openai/gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": texto}, "finish_reason": "stop"}],
        },
    )


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("tempo esgotado (simulado)", request=request)


CENARIOS = [
    {
        "id": "E01_sem_chave",
        "descricao": "OPENROUTER_API_KEY vazia: o helper nem tenta chamar a API.",
        "simulacao": "nenhuma (configuração sem chave)",
        "handler": None,
        "mensagem": PERGUNTA,
    },
    {
        "id": "E02_chave_invalida_401",
        "descricao": "Chave inválida: a API responde HTTP 401.",
        "simulacao": "MockTransport devolve 401 {\"error\": {\"message\": \"No auth credentials found\", \"code\": 401}}",
        "handler": lambda r: httpx.Response(401, json={"error": {"message": "No auth credentials found", "code": 401}}),
        "mensagem": PERGUNTA,
    },
    {
        "id": "E03_limite_429",
        "descricao": "Limite de requisições atingido: HTTP 429.",
        "simulacao": "MockTransport devolve 429",
        "handler": lambda r: httpx.Response(429, json={"error": {"message": "Rate limit exceeded", "code": 429}}),
        "mensagem": PERGUNTA,
    },
    {
        "id": "E04_erro_servidor_500",
        "descricao": "Instabilidade do provedor: HTTP 500.",
        "simulacao": "MockTransport devolve 500",
        "handler": lambda r: httpx.Response(500, text="Internal Server Error"),
        "mensagem": PERGUNTA,
    },
    {
        "id": "E05_timeout",
        "descricao": "O provedor não responde dentro de ASSISTANT_TIMEOUT_SECONDS.",
        "simulacao": "MockTransport levanta httpx.ReadTimeout",
        "handler": _timeout,
        "mensagem": PERGUNTA,
    },
    {
        "id": "E06_resposta_vazia",
        "descricao": "O provedor devolve 200 com conteúdo vazio.",
        "simulacao": "MockTransport devolve 200 com message.content = \"\"",
        "handler": lambda r: _resposta_ok(""),
        "mensagem": PERGUNTA,
    },
    {
        "id": "E07_json_invalido",
        "descricao": "O provedor devolve 200 com corpo que não é JSON.",
        "simulacao": "MockTransport devolve 200 com texto '<html>erro</html>'",
        "handler": lambda r: httpx.Response(200, text="<html>erro</html>"),
        "mensagem": PERGUNTA,
    },
    {
        "id": "E08_protocolo_inexistente",
        "descricao": "Protocolo pedido não existe: o backend envia protocolo_solicitado sem denúncia.",
        "simulacao": "nenhuma (configuração sem chave); denuncia=None",
        "handler": None,
        "mensagem": "Qual o status do protocolo AC-2026-000999?",
        "protocolo": "AC-2026-000999",
    },
    {
        "id": "E09_guardrail_protocolo_inventado",
        "descricao": "O modelo cita um protocolo que não foi fornecido: a resposta é descartada.",
        "simulacao": "MockTransport devolve 200 com texto que cita AC-2026-000777 (não fornecido)",
        "handler": lambda r: _resposta_ok("Sua denúncia AC-2026-000777 está Resolvida desde ontem."),
        "mensagem": "Como está minha denúncia?",
    },
    {
        "id": "E10_guardrail_rota_acessivel",
        "descricao": "O modelo afirma que uma rota é acessível: a resposta é descartada.",
        "simulacao": "MockTransport devolve 200 com 'Sim, a rota pela Rua Exemplo é acessível.'",
        "handler": lambda r: _resposta_ok("Sim, a rota pela Rua Exemplo é totalmente acessível para cadeirantes."),
        "mensagem": "A rota pela Rua Exemplo é acessível para cadeirante?",
    },
]


def _erro_cliente(handler) -> dict | None:
    if handler is None:
        return None
    client = OpenRouterClient(
        api_key=CHAVE_FICTICIA,
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    try:
        client.chat([{"role": "user", "content": "teste"}])
    except LLMError as exc:
        return {
            "excecao": type(exc).__name__,
            "codigo": exc.code,
            "status_http": exc.status_code,
            "mensagem": str(exc),
            "chave_aparece_na_mensagem": CHAVE_FICTICIA in str(exc) or CHAVE_FICTICIA in repr(exc),
        }
    return {"excecao": None, "observacao": "o cliente não levantou exceção (resposta HTTP aceita)"}


def main() -> None:
    meta = metadados(script="gerar_exemplos_erros.py", rede="nenhuma (httpx.MockTransport)")
    resultados = []
    md = [
        "# Exemplos reais de tratamento de erros — AcessaCidade Helper",
        "",
        "Gerado por `examples/gerar_exemplos_erros.py`. As falhas da API são **simuladas** com",
        "`httpx.MockTransport` (sem rede, sem chave real). As respostas abaixo foram produzidas",
        "executando o código do helper.",
        "",
        f"- Gerado em (UTC): `{meta['gerado_em']}`",
        f"- Versão do helper: `{meta['versao_helper']}` — Python `{meta['python']}`",
        "",
    ]
    for cen in CENARIOS:
        handler = cen["handler"]
        if handler is None:
            svc = AssistantService(HelperConfig(api_key=""))
        else:
            svc = AssistantService(HelperConfig(api_key=CHAVE_FICTICIA), transport=httpx.MockTransport(handler))
        req = AssistantRequest(mensagem=cen["mensagem"], protocolo_solicitado=cen.get("protocolo"))
        resp = svc.answer(req).to_dict()
        erro = _erro_cliente(handler)
        item = {
            "id": cen["id"],
            "descricao": cen["descricao"],
            "simulacao": cen["simulacao"],
            "llm_habilitado": svc.llm_enabled,
            "mensagem": cen["mensagem"],
            "protocolo_solicitado": cen.get("protocolo"),
            "erro_do_cliente_llm": erro,
            "resposta_do_helper": resp,
        }
        resultados.append(item)
        md += [
            f"## {cen['id']}",
            "",
            f"- **Cenário:** {cen['descricao']}",
            f"- **Simulação:** {cen['simulacao']}",
            f"- **LLM habilitado:** `{svc.llm_enabled}`",
            f"- **Mensagem:** {cen['mensagem']}",
        ]
        if erro:
            md.append(f"- **Exceção do cliente LLM:** `{json.dumps(erro, ensure_ascii=False)}`")
        md += [
            f"- **Fonte da resposta:** `{resp['fonte']}`",
            "",
            "```text",
            resp["resposta"],
            "```",
            "",
            "**Avisos:**",
        ]
        md += [f"- {a}" for a in resp["avisos"]] + [""]
    caminhos = salvar(PASTA_EXEMPLOS / "erros", "exemplos_erros", {"metadados": meta, "resultados": resultados}, "\n".join(md))
    for c in caminhos:
        print(f"salvo: {c}")
    print(f"{len(resultados)} cenários; fontes: {[r['resposta_do_helper']['fonte'] for r in resultados]}")


if __name__ == "__main__":
    main()
