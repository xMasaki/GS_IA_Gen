"""Indicadores operacionais em tempo real (contrato, seção 4.6), calculados a partir do SQLite."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .. import domain as d
from .denuncias import ServicoDenuncias

ORDEM_VISAO = ("POSSIBLE_POTHOLE", "INCONCLUSIVE", "NOT_IDENTIFIED")


def _por_enum(contagem: Counter, mapa: dict[str, str], ordenar_por_total: bool) -> list[dict]:
    itens = [{"chave": k, "rotulo": r, "total": int(contagem.get(k, 0))} for k, r in mapa.items()]
    extras = [k for k in contagem if k not in mapa]
    itens += [{"chave": k, "rotulo": k, "total": int(contagem[k])} for k in sorted(extras)]
    if ordenar_por_total:
        itens.sort(key=lambda i: -i["total"])  # sort estável: empates mantêm a ordem do contrato
    return itens


class ServicoIndicadores:
    def __init__(self, denuncias: ServicoDenuncias) -> None:
        self.denuncias = denuncias

    def calcular(self, incluir_simulados: bool = True) -> dict[str, Any]:
        linhas = self.denuncias.repo.todas(incluir_simulados)
        visao = Counter(r["visao_classificacao"] or d.SEM_IMAGEM for r in linhas)
        bairros = Counter(r["bairro"] for r in linhas)
        dias = Counter((r["criado_em"] or "")[:10] for r in linhas if r["criado_em"])
        origens = Counter(r["origem"] for r in linhas)

        recentes = sorted(linhas, key=lambda r: (r["criado_em"], r["id"]), reverse=True)[:5]
        mapa_visao = {k: d.CLASSIFICACOES_VISAO[k] for k in ORDEM_VISAO}
        mapa_visao[d.SEM_IMAGEM] = d.ROTULO_SEM_FOTO

        return {
            "total": len(linhas),
            "possiveis_buracos": int(visao.get("POSSIBLE_POTHOLE", 0)),
            "inconclusivas": int(visao.get("INCONCLUSIVE", 0)),
            "nao_identificadas": int(visao.get("NOT_IDENTIFIED", 0)),
            "sem_imagem": int(visao.get(d.SEM_IMAGEM, 0)),
            "por_categoria": _por_enum(Counter(r["tipo_obstaculo"] for r in linhas), d.TIPOS_OBSTACULO, True),
            "por_bairro": [
                {"chave": b, "rotulo": b, "total": t}
                for b, t in sorted(bairros.items(), key=lambda kv: (-kv[1], kv[0].lower()))
            ],
            "por_status": _por_enum(Counter(r["status"] for r in linhas), d.STATUS, False),
            "por_resultado_visao": _por_enum(visao, mapa_visao, False),
            "por_origem": [
                {"chave": o, "rotulo": o, "total": t}
                for o, t in sorted(origens.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "por_dia": [{"data": dia, "total": t} for dia, t in sorted(dias.items())],
            "recentes": [self.denuncias.para_publico(r) for r in recentes],
            "inclui_simulados": incluir_simulados,
            "gerado_em": d.agora_iso(),
        }

    def resumo(self, incluir_simulados: bool = True) -> dict[str, Any]:
        """Versão enxuta (sem `recentes`) entregue ao assistente."""
        completo = self.calcular(incluir_simulados)
        completo.pop("recentes", None)
        return completo
