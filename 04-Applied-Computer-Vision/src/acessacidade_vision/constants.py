"""Constantes públicas e parâmetros (limiares) da triagem por visão computacional.

Todos os limiares ficam centralizados aqui para que a regra de classificação seja
explicável, auditável e documentada (ver docs/DOCUMENTACAO_TECNICA_TRANSFORMACOES.md).
"""

from __future__ import annotations

ALGORITHM_VERSION = "1.0.0"

# Ordem oficial das etapas (contrato de integração, seção 4.1 / 5).
STAGE_ORDER = ("original", "cinza", "filtrada", "contraste", "bordas", "mascara", "contornos")

POSSIBLE_POTHOLE = "POSSIBLE_POTHOLE"
NOT_IDENTIFIED = "NOT_IDENTIFIED"
INCONCLUSIVE = "INCONCLUSIVE"

# Rótulos exibidos na interface (contrato, seção 3.4).
CLASS_LABELS = {
    POSSIBLE_POTHOLE: "Possível buraco identificado",
    NOT_IDENTIFIED: "Nenhum indício suficiente de buraco",
    INCONCLUSIVE: "Análise inconclusiva",
}

AVISO = "Triagem automática inicial. Não substitui avaliação técnica; requer revisão humana."

# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------
MIN_DIMENSION = 64          # px — menor lado aceito
MAX_DIMENSION = 8000        # px — maior lado aceito
DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # limite usado por analyze_image quando chamado diretamente

# ---------------------------------------------------------------------------
# Pré-processamento
# ---------------------------------------------------------------------------
WORK_MAX_SIDE = 800          # px — a análise é feita numa cópia com este maior lado
GAUSSIAN_KSIZE = 5           # kernel 5x5
GAUSSIAN_SIGMA = 1.1         # desvio-padrão do kernel gaussiano
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (4, 4)
# Suavização gaussiana MAIS forte usada só para segmentar (limiarizar): σ = 3 px apaga a
# granulação de pedras/asfalto/folhas (escala ~ 2-5 px) mantendo a forma de regiões de
# dezenas de pixels. As medidas de textura/contraste continuam usando a imagem σ = 1,1.
SEGMENTATION_SIGMA = 3.0

# ---------------------------------------------------------------------------
# Portões de qualidade (imagem inadequada -> INCONCLUSIVE)
# ---------------------------------------------------------------------------
QUALITY = {
    "brilho_minimo": 45.0,          # média de cinza (0-255) abaixo disto = muito escura
    "brilho_maximo": 215.0,         # média de cinza acima disto = muito clara / estourada
    "contraste_minimo": 7.0,        # desvio-padrão (RMS) de cinza abaixo disto = baixo contraste
    "nitidez_minima": 30.0,         # variância do Laplaciano abaixo disto = borrada
    "saturacao_maxima_pct": 35.0,   # % de pixels >= 250 acima disto = estourada
    "escuros_maximo_pct": 60.0,     # % de pixels <= 20 acima disto = muito escura
}

# ---------------------------------------------------------------------------
# Segmentação
# ---------------------------------------------------------------------------
SEGMENTATION = {
    "k_robusto": 2.5,          # limiar robusto = mediana - k * sigma_robusto (MAD)
    "delta_minimo": 28.0,      # a região precisa ser pelo menos isto mais escura que a mediana
    "eta_bimodal": 0.85,       # efetividade de Otsu a partir da qual o histograma é claramente bimodal
    "fracao_escura_bimodal": 0.30,  # ...com a população escura ocupando >= 30% da foto (sombra extensa)
    "canny_sigma_pre": 1.5,    # suavização extra antes do Canny (o CLAHE realça a granulação)
    "canny_baixo": 40,
    "canny_alto": 110,
    "canny_percentil": 94.0,   # limiar alto do Canny = max(110, percentil 94 do gradiente)
    "canny_razao_baixo": 0.36, # limiar baixo = max(40, 0,36 · alto)
    "abertura_kernel": 5,      # elipse 5x5 — remove pontos e rachaduras finas
    "abertura_iteracoes": 2,
    "fechamento_kernel": 11,   # elipse 11x11 — une fragmentos da mesma região
    "area_minima_rel": 0.004,  # 0,4% da imagem — abaixo disto o contorno é ignorado
    "max_candidatas": 8,
    "banda_borda_px": 5,       # espessura da faixa usada para medir bordas no contorno
    # --- multi-limiar (ver segmentation.threshold_levels) ---
    "teto_delta_rel": 0.55,    # limiar "robusto" nunca fica abaixo de (1 - 0,55) · mediana
    "fracao_relativa": 0.70,   # nível "relativo": 70% da mediana
    "limiar_minimo": 12.0,     # níveis abaixo disto (quase preto) são descartados
    "fusao_limiares": 4.0,     # níveis a menos de 4 tons de cinza um do outro são fundidos
    "iou_fusao": 0.60,         # candidatas de níveis diferentes com IoU >= 0,6 são a mesma região
}

# ---------------------------------------------------------------------------
# Classificação (regra explicável)
# ---------------------------------------------------------------------------
CLASSIFIER = {
    # portões geométricos/fotométricos (critérios mínimos)
    "area_rel_min": 0.006,
    "area_rel_max": 0.45,
    "solidez_min": 0.60,
    "alongamento_max": 4.0,
    "contraste_min": 0.18,
    # decisão pela pontuação heurística
    "limiar_possivel_buraco": 0.60,
    "limiar_inconclusivo": 0.42,
    # pesos da pontuação (somam 1.0)
    "pesos": {
        "contraste": 0.20,
        "borda": 0.20,
        "textura": 0.25,
        "profundidade": 0.15,
        "forma": 0.20,
    },
    # penalidade quando o contorno encosta na borda da imagem (sombras costumam encostar)
    "penalidade_borda_imagem": 0.5,
    # penalidade suave para regiões no topo do quadro (fachada/horizonte, não o piso):
    # fator = 1 - penalidade · (1 - rampa(centro_y_relativo, inicio, fim))
    "penalidade_topo": 0.4,
    "topo_inicio": 0.15,
    "topo_fim": 0.35,
    # máscara escura cobrindo grande parte da imagem -> ambiguidade
    "mascara_ambigua_pct": 50.0,
}
