"""Segmentação: limiarização das regiões escuras, detecção de bordas (Canny),
morfologia matemática e extração de contornos.
"""

from __future__ import annotations

import cv2
import numpy as np

from .constants import SEGMENTATION


def robust_sigma(values: np.ndarray) -> tuple[float, float]:
    """Mediana e desvio robusto (1,4826 · MAD) — pouco sensíveis à própria região escura."""
    v = values.astype(np.float64).ravel()
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    return med, 1.4826 * mad


def otsu_threshold(gray: np.ndarray) -> tuple[float, float]:
    """Limiar de Otsu e a efetividade η = σ²_entre / σ²_total (0..1).

    Otsu escolhe o limiar t que maximiza a variância entre as classes
    "escura" e "clara". η próximo de 1 indica histograma bimodal (duas populações
    bem separadas); η baixo indica uma única população (piso uniforme).
    """
    t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    g = gray.astype(np.float64).ravel()
    total_var = float(g.var())
    if total_var <= 1e-9:
        return float(t), 0.0
    low, high = g[g <= t], g[g > t]
    if low.size == 0 or high.size == 0:
        return float(t), 0.0
    w0, w1 = low.size / g.size, high.size / g.size
    between = w0 * w1 * (low.mean() - high.mean()) ** 2
    return float(t), float(between / total_var)


def dark_region_threshold(gray: np.ndarray) -> dict:
    """Combina Otsu com um limiar estatístico robusto.

    limiar_aplicado = min(limiar_otsu, mediana − max(delta_minimo, k · σ_robusto))

    O termo robusto garante que só sejam marcados pixels *claramente* mais escuros
    que o piso predominante; o Otsu garante a separação entre as duas populações
    quando o histograma é bimodal.
    """
    med, sig = robust_sigma(gray)
    t_otsu, eta = otsu_threshold(gray)
    t_rob = med - max(SEGMENTATION["delta_minimo"], SEGMENTATION["k_robusto"] * sig)
    dark_frac = float(np.count_nonzero(gray <= t_otsu)) / float(gray.size)
    # Histograma claramente bimodal com população escura grande (ex.: sombra extensa):
    # a mediana deixa de representar o piso, então usa-se o Otsu para que a região
    # escura apareça como candidata e seja avaliada (e explicada) pela regra.
    bimodal = eta >= SEGMENTATION["eta_bimodal"] and dark_frac >= SEGMENTATION["fracao_escura_bimodal"]
    t = max(0.0, t_otsu if bimodal else min(t_otsu, t_rob))
    return {
        "histograma_bimodal_extenso": bool(bimodal),
        "fracao_escura_otsu": round(dark_frac, 4),
        "mediana_cinza": round(med, 2),
        "sigma_robusto": round(sig, 2),
        "limiar_otsu": round(t_otsu, 2),
        "efetividade_otsu": round(eta, 4),
        "limiar_robusto": round(t_rob, 2),
        "limiar_aplicado": round(t, 2),
    }


def multi_otsu_dark_threshold(gray: np.ndarray) -> float:
    """Menor limiar do Otsu de 3 classes (escuro / médio / claro), calculado no histograma.

    O Otsu clássico divide o histograma em 2 populações; em fotos reais (buraco escuro +
    piso médio + céu/faixa/pedras claras) o corte de 2 classes cai no meio do piso. Com 3
    classes o primeiro limiar t1 isola a população mais escura — onde fica o fundo do
    buraco. Maximiza a variância entre classes σ²_B = Σ w_k (μ_k − μ_T)² para (t1, t2),
    por varredura vetorizada de todos os pares sobre o histograma de 256 faixas.
    """
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    p = hist / max(1.0, hist.sum())
    levels = np.arange(256, dtype=np.float64)
    cum_p = np.cumsum(p)
    cum_m = np.cumsum(p * levels)
    mt = cum_m[-1]
    t1 = np.arange(256)[:, None]
    t2 = np.arange(256)[None, :]
    w0 = cum_p[t1]
    w1 = cum_p[t2] - cum_p[t1]
    w2 = 1.0 - cum_p[t2]
    valid = (t2 > t1) & (w0 > 1e-6) & (w1 > 1e-6) & (w2 > 1e-6)
    with np.errstate(divide="ignore", invalid="ignore"):
        m0 = cum_m[t1] / w0
        m1 = (cum_m[t2] - cum_m[t1]) / w1
        m2 = (mt - cum_m[t2]) / w2
        between = w0 * (m0 - mt) ** 2 + w1 * (m1 - mt) ** 2 + w2 * (m2 - mt) ** 2
    between = np.where(valid, between, -1.0)
    i, _ = np.unravel_index(int(np.argmax(between)), between.shape)
    return float(i)


def threshold_levels(gray: np.ndarray) -> tuple[dict, list[dict]]:
    """Vários níveis de limiarização (multi-limiar) + estatísticas do histograma.

    Um único limiar global não serve para fotos de cenas diferentes: com fundo variado
    (calçada, meio-fio, pessoas, céu) o desvio-padrão da foto é grande e o limiar
    estatístico cai para perto de zero; já o Otsu de 2 classes sobe demais quando há
    piso claro e escuro. Em vez de apostar num valor, a análise testa uma pequena
    família de limiares derivados do histograma e deixa a **regra de classificação**
    (forma, contraste, bordas, textura) escolher a região mais parecida com buraco:

    - ``legado``  : min(Otsu, mediana − max(Δ, k·σ_robusto)) — regra original;
    - ``otsu``    : Otsu de 2 classes;
    - ``multiotsu``: 1º limiar do Otsu de 3 classes (população mais escura);
    - ``robusto`` : mediana − min(max(Δ, k·σ_robusto), 55% da mediana) — o teto impede
      que cenas muito heterogêneas empurrem o limiar para ~0;
    - ``relativo``: 70% da mediana (regiões ≥ 30% mais escuras que o piso típico).

    Retorna ``(estatisticas, niveis)``; ``estatisticas`` mantém as chaves históricas
    (``limiar_otsu``, ``limiar_robusto`` ...). Níveis com valores quase iguais são fundidos.
    """
    med, sig = robust_sigma(gray)
    t_otsu, eta = otsu_threshold(gray)
    t_multi = multi_otsu_dark_threshold(gray)
    delta = max(SEGMENTATION["delta_minimo"], SEGMENTATION["k_robusto"] * sig)
    t_rob = med - delta
    dark_frac = float(np.count_nonzero(gray <= t_otsu)) / float(gray.size)
    bimodal = eta >= SEGMENTATION["eta_bimodal"] and dark_frac >= SEGMENTATION["fracao_escura_bimodal"]
    t_legacy = t_otsu if bimodal else min(t_otsu, t_rob)
    t_capped = med - min(delta, SEGMENTATION["teto_delta_rel"] * med)

    raw = [
        ("legado", t_legacy),
        ("otsu", t_otsu),
        ("multiotsu", t_multi),
        ("robusto", t_capped),
        ("relativo", SEGMENTATION["fracao_relativa"] * med),
    ]
    levels: list[dict] = []
    for name, value in raw:
        value = float(max(0.0, min(254.0, value)))
        if value < SEGMENTATION["limiar_minimo"]:
            continue  # quase preto: nada é "mais escuro" que isto
        if any(abs(value - lv["valor"]) <= SEGMENTATION["fusao_limiares"] for lv in levels):
            continue
        levels.append({"nome": name, "valor": round(value, 2)})
    if not levels:  # foto praticamente preta: mantém um nível para a regra de qualidade/decisão
        levels.append({"nome": "legado", "valor": round(max(0.0, t_legacy), 2)})

    stats = {
        "histograma_bimodal_extenso": bool(bimodal),
        "fracao_escura_otsu": round(dark_frac, 4),
        "mediana_cinza": round(med, 2),
        "sigma_robusto": round(sig, 2),
        "limiar_otsu": round(t_otsu, 2),
        "limiar_multiotsu": round(t_multi, 2),
        "efetividade_otsu": round(eta, 4),
        "limiar_robusto": round(t_rob, 2),
        "limiar_aplicado": levels[0]["valor"],
    }
    return stats, levels


def threshold_dark(gray: np.ndarray, threshold: float) -> np.ndarray:
    """Máscara binária: 255 onde o pixel é mais escuro que o limiar (limiarização inversa)."""
    return np.where(gray <= threshold, 255, 0).astype(np.uint8)


def canny_thresholds(smooth: np.ndarray) -> tuple[float, float]:
    """Limiares de histerese adaptativos ao "nível de ocupação" da foto.

    Limiares fixos (40/110) funcionam em imagens limpas, mas numa foto real de calçada
    (pedras, folhas, juntas) 7–15% dos pixels viram "borda" e o contorno do buraco some no
    meio do emaranhado. O limiar alto passa a ser ``max(110, percentil 94 do módulo do
    gradiente de Sobel)``: em imagens limpas permanece 110; em cenas carregadas sobe e
    mantém só as transições realmente fortes. O limiar baixo é ≈ 0,36 × o alto (razão
    clássica de 1:2,5 a 1:3 entre os dois).
    """
    f = smooth.astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    high = max(float(SEGMENTATION["canny_alto"]), float(np.percentile(mag, SEGMENTATION["canny_percentil"])))
    low = max(float(SEGMENTATION["canny_baixo"]), SEGMENTATION["canny_razao_baixo"] * high)
    return low, high


def detect_edges(gray: np.ndarray) -> np.ndarray:
    """Detector de bordas de Canny sobre a imagem realçada.

    Antes do Canny aplica-se uma suavização gaussiana extra (σ = 1,5) porque o CLAHE
    também realça a granulação do piso; sem ela o asfalto vira um "tapete" de bordas.
    O Canny calcula o gradiente (Sobel 3x3, norma L2), afina as bordas por supressão
    de não-máximos e liga os trechos por histerese com limiares adaptativos
    (ver :func:`canny_thresholds`; mínimos 40 e 110).
    """
    smooth = cv2.GaussianBlur(gray, (0, 0), SEGMENTATION["canny_sigma_pre"])
    low, high = canny_thresholds(smooth)
    return cv2.Canny(smooth, low, high, L2gradient=True)


def morphology(mask: np.ndarray) -> np.ndarray:
    """Abertura (erosão→dilatação) remove pontos isolados e rachaduras finas;
    fechamento (dilatação→erosão) une fragmentos da mesma região; por fim os
    furos internos são preenchidos."""
    k_open = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (SEGMENTATION["abertura_kernel"], SEGMENTATION["abertura_kernel"])
    )
    k_close = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (SEGMENTATION["fechamento_kernel"], SEGMENTATION["fechamento_kernel"])
    )
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open, iterations=SEGMENTATION["abertura_iteracoes"])
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, k_close, iterations=1)
    return fill_holes(closed)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def find_candidate_contours(mask: np.ndarray) -> list[np.ndarray]:
    """Contornos externos com área ≥ ``area_minima_rel`` da imagem, do maior para o menor."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    min_area = SEGMENTATION["area_minima_rel"] * mask.shape[0] * mask.shape[1]
    kept = [c for c in contours if cv2.contourArea(c) >= min_area]
    # ordem determinística: área decrescente, depois posição
    kept.sort(key=lambda c: (-cv2.contourArea(c), tuple(int(v) for v in cv2.boundingRect(c))))
    return kept[: SEGMENTATION["max_candidatas"]]
