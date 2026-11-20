"""Regra de classificação explicável (sem aprendizado de máquina).

Cada candidata recebe sub-pontuações entre 0 e 1, combinadas por pesos fixos
(``constants.CLASSIFIER["pesos"]``). A pontuação final é **heurística**: indica o
quanto a região se parece com um buraco segundo critérios geométricos e
fotométricos, e **não** é uma probabilidade calibrada.

Decisão:
1. Qualidade da foto inadequada (escura, clara, borrada, baixo contraste) → INCONCLUSIVE.
2. Sem candidata que passe nos critérios mínimos → NOT_IDENTIFIED.
3. Melhor candidata com pontuação ≥ 0,60 → POSSIBLE_POTHOLE.
4. Pontuação entre 0,42 e 0,60, ou região escura cobrindo grande parte da foto → INCONCLUSIVE.
5. Demais casos → NOT_IDENTIFIED.
"""

from __future__ import annotations

from .constants import CLASSIFIER, INCONCLUSIVE, NOT_IDENTIFIED, POSSIBLE_POTHOLE, SEGMENTATION


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _ramp(v: float, lo: float, hi: float) -> float:
    """0 em ``lo``, 1 em ``hi``, linear entre os dois."""
    return _clip01((v - lo) / (hi - lo))


def fmt_num(v: float, casas: int = 2) -> str:
    """Número no formato brasileiro (vírgula decimal)."""
    return f"{v:.{casas}f}".replace(".", ",")


def fmt_pct(frac: float, casas: int = 1) -> str:
    return fmt_num(100.0 * frac, casas) + "%"


def gate_failures(f: dict) -> list[str]:
    """Critérios mínimos que a candidata NÃO atende (lista vazia = atende todos)."""
    c = CLASSIFIER
    fails = []
    if f["area_relativa"] < c["area_rel_min"]:
        fails.append(f"área pequena ({fmt_pct(f['area_relativa'], 2)} da imagem; mínimo {fmt_pct(c['area_rel_min'], 1)})")
    if f["area_relativa"] > c["area_rel_max"]:
        fails.append(f"área grande demais ({fmt_pct(f['area_relativa'])} da imagem; máximo {fmt_pct(c['area_rel_max'], 0)})")
    if f["solidez"] < c["solidez_min"]:
        fails.append(f"forma muito recortada (solidez {fmt_num(f['solidez'])}; mínimo {fmt_num(c['solidez_min'])})")
    if f["alongamento"] > c["alongamento_max"]:
        fails.append(f"forma alongada, típica de rachadura ou junta (alongamento {fmt_num(f['alongamento'], 1)}; máximo {fmt_num(c['alongamento_max'], 1)})")
    if f["contraste_int_ext"] < c["contraste_min"]:
        fails.append(f"pouco mais escura que o entorno (contraste {fmt_pct(f['contraste_int_ext'], 0)}; mínimo {fmt_pct(c['contraste_min'], 0)})")
    return fails


def sub_scores(f: dict) -> dict:
    """Sub-pontuações 0..1 de cada critério."""
    forma = (
        0.4 * _ramp(f["solidez"], 0.55, 0.85)
        + 0.3 * (1.0 - _ramp(f["alongamento"], 2.0, 4.0))
        + 0.3 * _ramp(f["circularidade"], 0.15, 0.45)
    )
    return {
        "contraste": round(_ramp(f["contraste_int_ext"], 0.15, 0.45), 4),
        # metade pela densidade de bordas de Canny no contorno, metade pela nitidez da transição
        "borda": round(0.5 * _ramp(f["razao_bordas"], 1.0, 2.5) + 0.5 * _ramp(f["nitidez_borda"], 0.05, 0.12), 4),
        "textura": round(_ramp(f["textura_relativa"], 1.05, 1.8), 4),
        "profundidade": round(_ramp(f["gradiente_profundidade"], 0.0, 0.15), 4),
        "forma": round(_clip01(forma), 4),
    }


def score_candidate(f: dict) -> tuple[float, dict]:
    subs = sub_scores(f)
    pesos = CLASSIFIER["pesos"]
    score = sum(pesos[k] * subs[k] for k in pesos)
    # penalidade para regiões encostadas na moldura (comportamento típico de sombras)
    penal = 1.0 - CLASSIFIER["penalidade_borda_imagem"] * _ramp(f["fracao_toca_borda_imagem"], 0.10, 0.50)
    score *= penal
    subs["fator_borda_imagem"] = round(penal, 4)
    # penalidade suave para regiões no topo do quadro (provável fachada, não o chão)
    c = CLASSIFIER
    horizonte = 1.0 - c["penalidade_topo"] * (
        1.0 - _ramp(f.get("centro_y_relativo", 0.5), c["topo_inicio"], c["topo_fim"])
    )
    score *= horizonte
    subs["fator_topo_imagem"] = round(horizonte, 4)
    return round(_clip01(score), 4), subs


def describe_candidate(f: dict, subs: dict) -> list[str]:
    """Frases em português sobre a melhor candidata."""
    frases = [
        f"Região escura com área de {fmt_pct(f['area_relativa'])} da imagem "
        f"({f['area_px']} px), {fmt_pct(f['contraste_int_ext'], 0)} mais escura que o piso ao redor.",
        f"Forma: solidez {fmt_num(f['solidez'])}, circularidade {fmt_num(f['circularidade'])}, "
        f"alongamento {fmt_num(f['alongamento'], 1)}.",
    ]
    if subs["textura"] >= 0.5:
        frases.append(
            f"Textura interna mais irregular que a do piso (variação relativa {fmt_num(f['textura_relativa'])}x), "
            "compatível com fundo de buraco (cascalho, desnível)."
        )
    else:
        frases.append(
            f"Textura interna parecida com a do piso (variação relativa {fmt_num(f['textura_relativa'])}x): "
            "o piso parece apenas escurecido, como ocorre em sombras e manchas."
        )
    if subs["borda"] >= 0.5:
        frases.append(
            f"Borda abrupta e irregular no contorno ({fmt_num(f['razao_bordas'], 1)}x a densidade média de bordas da foto; "
            f"nitidez da transição {fmt_num(f['nitidez_borda'], 3)})."
        )
    else:
        frases.append(
            f"Contorno com transição suave ({fmt_num(f['razao_bordas'], 1)}x a densidade média de bordas; "
            f"nitidez {fmt_num(f['nitidez_borda'], 3)}), típico de sombra ou mancha."
        )
    if subs["profundidade"] >= 0.5:
        frases.append("O centro da região é mais escuro que as bordas internas, sugerindo profundidade.")
    if subs["fator_borda_imagem"] < 0.95:
        frases.append(
            f"A região encosta na moldura da foto ({fmt_pct(f['fracao_toca_borda_imagem'], 0)} do contorno), "
            "comportamento comum de sombras; a pontuação foi reduzida."
        )
    return frases


# ---------------------------------------------------------------------------
# Multi-limiar: fusão das candidatas de níveis diferentes e escolha do nível
# ---------------------------------------------------------------------------
def _bbox_iou(a: dict, b: dict) -> float:
    ax0, ay0, ax1, ay1 = a["x"], a["y"], a["x"] + a["largura"], a["y"] + a["altura"]
    bx0, by0, bx1, by1 = b["x"], b["y"], b["x"] + b["largura"], b["y"] + b["altura"]
    iw, ih = max(0, min(ax1, bx1) - max(ax0, bx0)), max(0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    union = a["largura"] * a["altura"] + b["largura"] * b["altura"] - inter
    return inter / union if union > 0 else 0.0


def merge_candidates(cands: list[dict]) -> list[dict]:
    """Funde candidatas de níveis de limiar diferentes que são a mesma região (IoU ≥ 0,6).

    Em cada grupo fica a melhor representante: preferem-se as que passam nos critérios
    mínimos e, entre elas, a de maior pontuação. ``niveis_confirmam`` registra em quantos
    níveis a região apareceu (uma região real tende a persistir em vários limiares;
    sombras e gradientes de iluminação mudam de tamanho). Resultado ordenado por área
    decrescente e limitado a ``max_candidatas``.
    """
    thr = SEGMENTATION["iou_fusao"]
    order = sorted(
        cands,
        key=lambda c: (bool(c["criterios_nao_atendidos"]), -c["pontuacao"], -c["area_px"], c["_nivel_idx"]),
    )
    groups: list[list[dict]] = []
    for c in order:
        for g in groups:
            if _bbox_iou(g[0], c) >= thr:
                g.append(c)
                break
        else:
            groups.append([c])
    merged = []
    for g in groups:
        rep = g[0]
        rep["niveis_confirmam"] = len({m["_nivel_idx"] for m in g})
        merged.append(rep)
    merged.sort(key=lambda c: (-c["area_px"], c["x"], c["y"]))
    return merged[: SEGMENTATION["max_candidatas"]]


def annotate_stability(cands: list[dict], n_levels: int) -> None:
    for c in cands:
        c["estabilidade"] = round(c["niveis_confirmam"] / max(1, n_levels), 3)


def pick_level(cands: list[dict]) -> int:
    """Índice do nível de limiar cuja máscara é exibida: o da melhor candidata válida
    (ou, se nenhuma é válida, o da maior candidata). Sem candidatas: o primeiro nível."""
    valid = [c for c in cands if not c["criterios_nao_atendidos"]]
    if valid:
        return max(valid, key=lambda c: c["pontuacao"])["_nivel_idx"]
    if cands:
        return cands[0]["_nivel_idx"]
    return 0


LIMITACOES = (
    "Limitação: sombras, manchas de óleo/umidade, rachaduras largas, poças e juntas escuras podem gerar "
    "falsos positivos; buracos rasos, cheios de água ou com a mesma cor do piso podem não ser detectados."
)


def classify(quality_issues: list[str], candidates: list[dict], mask_pct: float) -> dict:
    """Aplica a regra de decisão e devolve classificação, pontuação e explicações."""
    c = CLASSIFIER
    reasons: list[str] = []
    best = candidates[0] if candidates else None
    score = best["pontuacao"] if best else 0.0

    if quality_issues:
        reasons.append("A qualidade da fotografia não permite uma triagem confiável:")
        reasons.extend(quality_issues)
        if best:
            reasons.append(
                f"A melhor região encontrada teria pontuação heurística {fmt_num(score)}, "
                "mas o resultado foi marcado como inconclusivo por causa da qualidade da foto."
            )
        reasons.append("Envie outra foto, com boa iluminação, foco no piso e o celular estável.")
        reasons.append(LIMITACOES)
        return {"classification": INCONCLUSIVE, "score": score, "reasons": reasons, "decisao": "qualidade"}

    valid = [cd for cd in candidates if not cd["criterios_nao_atendidos"]]
    if not candidates:
        reasons.append(
            "Nenhuma região suficientemente mais escura que o piso foi encontrada após a limiarização e a morfologia."
        )
        reasons.append("O piso parece uniforme na fotografia; nenhum indício suficiente de buraco.")
        reasons.append(LIMITACOES)
        return {"classification": NOT_IDENTIFIED, "score": 0.0, "reasons": reasons, "decisao": "sem_candidatas"}

    if not valid:
        b = candidates[0]
        reasons.append(
            f"{len(candidates)} região(ões) escura(s) encontrada(s), mas nenhuma atende aos critérios mínimos de buraco."
        )
        reasons.append("Maior região descartada por: " + "; ".join(b["criterios_nao_atendidos"]) + ".")
        reasons.append(LIMITACOES)
        return {
            "classification": NOT_IDENTIFIED,
            "score": min(score, round(c["limiar_inconclusivo"] - 0.01, 4)),
            "reasons": reasons,
            "decisao": "criterios_minimos",
        }

    best = max(valid, key=lambda cd: cd["pontuacao"])
    score = best["pontuacao"]
    reasons.extend(describe_candidate(best, best["subpontuacoes"]))
    if mask_pct > c["mascara_ambigua_pct"]:
        reasons.insert(
            0,
            f"Regiões escuras cobrem {fmt_num(mask_pct, 0)}% da foto (iluminação irregular ou sombra extensa): "
            "não é possível separar um buraco do restante com segurança.",
        )
        reasons.append(f"Pontuação heurística {fmt_num(score)} (não é probabilidade).")
        reasons.append(LIMITACOES)
        return {"classification": INCONCLUSIVE, "score": score, "reasons": reasons, "decisao": "ambiguidade_mascara"}

    if score >= c["limiar_possivel_buraco"]:
        reasons.insert(
            0,
            f"Pontuação heurística {fmt_num(score)} ≥ {fmt_num(c['limiar_possivel_buraco'])}: a região atende aos critérios "
            "geométricos e fotométricos de um possível buraco (não é probabilidade).",
        )
        cls, dec = POSSIBLE_POTHOLE, "pontuacao_alta"
    elif score >= c["limiar_inconclusivo"]:
        reasons.insert(
            0,
            f"Pontuação heurística {fmt_num(score)} entre {fmt_num(c['limiar_inconclusivo'])} e "
            f"{fmt_num(c['limiar_possivel_buraco'])}: há uma região suspeita, mas os indícios são ambíguos.",
        )
        cls, dec = INCONCLUSIVE, "pontuacao_intermediaria"
    else:
        reasons.insert(
            0,
            f"Pontuação heurística {fmt_num(score)} < {fmt_num(c['limiar_inconclusivo'])}: a região escura "
            "não reúne indícios suficientes de buraco.",
        )
        cls, dec = NOT_IDENTIFIED, "pontuacao_baixa"
    reasons.append(LIMITACOES)
    return {"classification": cls, "score": score, "reasons": reasons, "decisao": dec}
