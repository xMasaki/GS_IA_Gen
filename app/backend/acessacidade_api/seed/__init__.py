"""Carga das denúncias de demonstração (SIMULADAS) — somente quando a tabela está vazia.

Para itens com foto, a imagem SINTÉTICA correspondente de ``data/samples/fotos/`` é
processada DE VERDADE pelo pacote de visão (resultado real, não inventado). Se a pasta
ou o arquivo não existir (ex.: imagem Docker sem amostras), a denúncia é criada sem foto.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import HTTPException

from .. import domain as d

logger = logging.getLogger("acessacidade.seed")

SEED_PATH = Path(__file__).with_name("denuncias_demo.json")


def carregar_seed(servico, fotos_dir: Path, caminho: Path = SEED_PATH) -> int:
    """Insere o seed se não houver nenhuma denúncia. Devolve quantas foram inseridas."""
    if servico.repo.contar() > 0:
        return 0
    doc = json.loads(caminho.read_text(encoding="utf-8"))
    inseridas = 0
    for item in sorted(doc.get("denuncias", []), key=lambda i: i["criado_em"]):
        status = item.get("status", "RECEBIDA")
        if status not in d.STATUS_SEED_PERMITIDOS:
            status = "RECEBIDA"
        triagem = None
        foto = item.get("foto")
        if foto and servico.visao.disponivel:
            arquivo = (fotos_dir / Path(foto).name)
            if arquivo.is_file():
                try:
                    triagem = servico.visao.triar(arquivo.read_bytes())
                except HTTPException:
                    triagem = None
        if triagem is None and status == "AGUARDANDO_REVISAO":
            status = "RECEBIDA"  # sem triagem não faz sentido "aguardando revisão"
        dados = {
            "nome": None,
            "logradouro": item["logradouro"],
            "numero": item.get("numero"),
            "bairro": item["bairro"],
            "cidade": item.get("cidade") or "Cidade Exemplo",
            "ponto_referencia": item.get("ponto_referencia"),
            "tipo_obstaculo": item["tipo_obstaculo"],
            "descricao": item["descricao"],
            "impacto": item["impacto"],
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "origem": "SIMULADO",
            "consentimento": 1,
        }
        servico.registrar(
            dados, triagem, criado_em=item["criado_em"], simulado=True,
            status_final=status, observacao_final=item.get("observacao_status") or "Atualização simulada",
        )
        inseridas += 1
    logger.info("seed carregado", extra={"evento": "seed_carregado", "total": inseridas})
    return inseridas
