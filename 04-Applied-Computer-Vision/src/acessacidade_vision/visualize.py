"""Desenho das imagens de saída (contornos, caixas delimitadoras e rótulos)."""

from __future__ import annotations

import cv2
import numpy as np

# Cores em BGR. Vermelho = possível buraco; laranja = suspeita; cinza-azulado = descartada.
COLOR_POTHOLE = (40, 40, 230)
COLOR_SUSPECT = (0, 165, 255)
COLOR_REJECTED = (200, 160, 60)

_ASCII_LABELS = {
    "POSSIBLE_POTHOLE": "POSSIVEL BURACO",
    "NOT_IDENTIFIED": "NAO IDENTIFICADO",
    "INCONCLUSIVE": "INCONCLUSIVO",
}


def _put_label(img: np.ndarray, text: str, org: tuple[int, int], color: tuple[int, int, int], scale: float) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    thick = max(1, int(round(scale * 2)))
    (tw, th), base = cv2.getTextSize(text, font, scale, thick)
    x, y = org
    h, w = img.shape[:2]
    x = max(0, min(x, w - tw - 4))
    y = max(th + 4, min(y, h - base - 2))
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 4, y + base), color, thickness=cv2.FILLED)
    cv2.putText(img, text, (x + 2, y - 2), font, scale, (255, 255, 255), thick, cv2.LINE_AA)


def draw_contours_stage(
    img_bgr: np.ndarray,
    contours: list[np.ndarray],
    candidates: list[dict],
    detections_idx: set[int],
    classification: str,
    score: float,
    suspect: bool,
) -> np.ndarray:
    """Imagem "contornos": todos os contornos candidatos, caixas e rótulos (texto sem acentos,
    pois a fonte Hershey do OpenCV só desenha ASCII)."""
    out = img_bgr.copy()
    h, w = out.shape[:2]
    scale = max(0.45, min(1.0, w / 1000.0))
    for i, (cnt, cand) in enumerate(zip(contours, candidates)):
        if i in detections_idx:
            color = COLOR_SUSPECT if suspect else COLOR_POTHOLE
            label = ("Suspeita " if suspect else "Possivel buraco ") + f"{cand['pontuacao']:.2f}"
            thickness = 3
        else:
            color = COLOR_REJECTED
            label = f"Descartada {cand['pontuacao']:.2f}"
            thickness = 1
        cv2.drawContours(out, [cnt], -1, color, thickness)
        x, y, bw, bh = cand["x"], cand["y"], cand["largura"], cand["altura"]
        cv2.rectangle(out, (x, y), (x + bw, y + bh), color, max(1, thickness - 1))
        _put_label(out, label, (x, y - 4), color, scale * 0.8)
    header = f"{_ASCII_LABELS.get(classification, classification)} | pontuacao {score:.2f} (heuristica)"
    _put_label(out, header, (6, int(28 * scale) + 6), (40, 40, 40), scale * 0.8)
    return out


def montage(stages: dict[str, np.ndarray], order, cols: int = 4, cell_w: int = 400) -> np.ndarray:
    """Painel com todas as etapas lado a lado (usado pelos scripts e pela documentação)."""
    tiles = []
    for name in order:
        im = stages[name]
        if im.ndim == 2:
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        scale = cell_w / im.shape[1]
        im = cv2.resize(im, (cell_w, int(round(im.shape[0] * scale))), interpolation=cv2.INTER_AREA)
        im = cv2.copyMakeBorder(im, 30, 4, 4, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(im, name, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2, cv2.LINE_AA)
        tiles.append(im)
    th = max(t.shape[0] for t in tiles)
    tw = tiles[0].shape[1]
    tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    while len(tiles) % cols:
        tiles.append(np.full((th, tw, 3), 255, dtype=np.uint8))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)
