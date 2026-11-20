"""Extração de medidas (dados) de cada região candidata.

Para cada contorno são medidos:

- ``area_px`` / ``area_relativa``: área do contorno e fração da imagem;
- ``circularidade`` = 4π·A / P² (1 = círculo perfeito; formas finas ou recortadas → 0);
- ``solidez`` = A / área do fecho convexo (regiões compactas → perto de 1);
- ``razao_aspecto`` = largura / altura da caixa delimitadora;
- ``alongamento`` = lado maior / lado menor do retângulo de área mínima (rachaduras → alto);
- ``contraste_int_ext`` = (média_externa − média_interna) / média_externa;
- ``textura_relativa`` = CV_interno / CV_externo, com CV = desvio / média.
  Uma sombra ou mancha *escurece* o piso de forma multiplicativa e preserva o CV
  (≈ 1); o fundo de um buraco tem cascalho, desníveis e sombras internas (CV maior);
- ``densidade_bordas_contorno`` e ``razao_bordas``: fração de pixels de borda (Canny)
  numa faixa ao longo do contorno, e essa densidade dividida pela densidade global
  (borda "quebrada" e abrupta de buraco → alta; borda suave de mancha/sombra → baixa);
- ``gradiente_profundidade``: quanto o miolo da região é mais escuro que a faixa
  interna próxima à borda (buracos costumam escurecer em direção ao fundo);
- ``fracao_toca_borda_imagem``: fração do contorno encostada na moldura da foto;
- ``centro_y_relativo``: posição vertical do centro da caixa (0 = topo, 1 = base). Em foto
  oblíqua o quinto superior costuma ser fachada, horizonte ou céu, não o piso.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from .constants import SEGMENTATION


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return float(a) / float(b) if abs(float(b)) > 1e-9 else default


def prepare_context(gray: np.ndarray, filtered: np.ndarray, edges: np.ndarray) -> dict:
    """Mapas calculados uma única vez e reaproveitados para todas as candidatas."""
    g32 = gray.astype(np.float32)
    f32 = filtered.astype(np.float32)
    # textura fina (passa-alta): cinza − versão borrada (σ = 2,5 px)
    highpass = g32 - cv2.GaussianBlur(g32, (0, 0), 2.5)
    # magnitude do gradiente de Sobel 3x3 sobre a imagem filtrada
    gx = cv2.Sobel(f32, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f32, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy) / 8.0  # /8 normaliza o kernel de Sobel para níveis de cinza por pixel
    return {
        "gray": gray,
        "filtered": filtered,
        "edges": edges,
        "highpass": highpass,
        "grad": grad,
        "global_edge_density": float(np.count_nonzero(edges)) / float(edges.size),
    }


def contour_features(contour: np.ndarray, ctx: dict) -> dict:
    gray, filtered, edges = ctx["gray"], ctx["filtered"], ctx["edges"]
    highpass, grad = ctx["highpass"], ctx["grad"]
    global_edge_density = ctx["global_edge_density"]
    h, w = gray.shape[:2]
    area = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull))
    x, y, bw, bh = (int(v) for v in cv2.boundingRect(contour))
    (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
    long_side, short_side = max(rw, rh), max(1.0, min(rw, rh))

    region = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(region, [contour], -1, 255, thickness=cv2.FILLED)
    inside = region > 0

    # anel externo proporcional ao tamanho da região
    ring_px = int(max(7, min(40, 0.25 * math.sqrt(max(area, 1.0)))))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring_px + 1, 2 * ring_px + 1))
    outside = (cv2.dilate(region, k) > 0) & ~inside
    if not outside.any():  # região ocupa a imagem inteira
        outside = ~inside

    f_in = filtered[inside].astype(np.float64)
    f_out = filtered[outside].astype(np.float64)
    mean_in, mean_out = float(f_in.mean()), float(f_out.mean())
    contrast = _safe_div(mean_out - mean_in, max(mean_out, 1.0))

    # textura: só o miolo (sem a faixa do contorno) e o anel externo afastado do contorno
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    core_in = cv2.erode(region, k5) > 0
    if np.count_nonzero(core_in) < 30:
        core_in = inside
    far_out = outside & ~(cv2.dilate(region, k5) > 0)
    if np.count_nonzero(far_out) < 30:
        far_out = outside
    cv_in = _safe_div(float(highpass[core_in].std()), max(float(filtered[core_in].mean()), 1.0))
    cv_out = _safe_div(float(highpass[far_out].std()), max(float(filtered[far_out].mean()), 1.0))
    texture_ratio = _safe_div(cv_in, max(cv_out, 1e-3), default=1.0)

    # faixa ao longo do contorno (bordas abruptas x suaves)
    band = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(band, [contour], -1, 255, thickness=SEGMENTATION["banda_borda_px"])
    # descarta a parte da faixa colada na moldura da imagem
    m = 3
    band[:m, :] = 0
    band[-m:, :] = 0
    band[:, :m] = 0
    band[:, -m:] = 0
    band_px = int(np.count_nonzero(band))
    edge_density = _safe_div(np.count_nonzero((edges > 0) & (band > 0)), band_px)
    edge_ratio = _safe_div(edge_density, max(global_edge_density, 0.01))
    # nitidez da borda: gradiente médio na faixa (descontado o gradiente da textura do piso)
    # dividido pelo degrau de brilho; ~1/largura da transição em pixels
    step = max(mean_out - mean_in, 5.0)
    grad_band = float(grad[band > 0].mean()) if band_px else 0.0
    grad_far = float(grad[far_out].mean())
    edge_sharp = max(0.0, (grad_band - grad_far) / step)

    # gradiente de profundidade pelo mapa de distância à borda da região
    dist = cv2.distanceTransform(region, cv2.DIST_L2, 5)
    dmax = float(dist.max())
    depth = 0.0
    if dmax >= 4.0:
        core = dist >= 0.6 * dmax
        shell = (dist > 0.15 * dmax) & (dist <= 0.4 * dmax)
        if core.any() and shell.any():
            depth = _safe_div(
                float(filtered[shell].mean()) - float(filtered[core].mean()), max(mean_out, 1.0)
            )

    pts = contour.reshape(-1, 2)
    touching = (pts[:, 0] <= 2) | (pts[:, 1] <= 2) | (pts[:, 0] >= w - 3) | (pts[:, 1] >= h - 3)
    touch_frac = float(np.count_nonzero(touching)) / max(1, len(pts))

    return {
        "x": x,
        "y": y,
        "largura": bw,
        "altura": bh,
        "area_px": int(round(area)),
        "area_relativa": round(area / float(h * w), 4),
        "perimetro_px": round(perimeter, 1),
        "circularidade": round(_safe_div(4.0 * math.pi * area, perimeter ** 2), 4),
        "solidez": round(_safe_div(area, hull_area), 4),
        "razao_aspecto": round(_safe_div(bw, bh), 3),
        "alongamento": round(long_side / short_side, 3),
        "media_interna": round(mean_in, 2),
        "media_externa": round(mean_out, 2),
        "contraste_int_ext": round(contrast, 4),
        "textura_relativa": round(texture_ratio, 4),
        "densidade_bordas_contorno": round(edge_density, 4),
        "razao_bordas": round(edge_ratio, 4),
        "nitidez_borda": round(edge_sharp, 4),
        "gradiente_profundidade": round(depth, 4),
        "fracao_toca_borda_imagem": round(touch_frac, 4),
        "centro_y_relativo": round((y + bh / 2.0) / float(h), 4),
    }
