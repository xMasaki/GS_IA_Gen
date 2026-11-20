"""Pré-processamento: redimensionamento, tons de cinza, filtragem espacial,
avaliação de qualidade (brilho, contraste, nitidez), realce de contraste (CLAHE)
e correção opcional de perspectiva.
"""

from __future__ import annotations

import cv2
import numpy as np

from .constants import (
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_GRID,
    GAUSSIAN_KSIZE,
    GAUSSIAN_SIGMA,
    QUALITY,
    WORK_MAX_SIDE,
)
from .errors import VisionError
from .privacy import resize_max_side


def resize_for_analysis(img: np.ndarray, max_side: int = WORK_MAX_SIDE) -> tuple[np.ndarray, float]:
    """Cópia de trabalho com maior lado ``max_side`` (interpolação por área).

    Trabalhar sempre na mesma escala torna os limiares (nitidez, áreas, kernels)
    comparáveis entre fotos de celulares diferentes.
    """
    return resize_max_side(img, max_side)


def to_gray(img_bgr: np.ndarray) -> np.ndarray:
    """Luminância: Y = 0,299·R + 0,587·G + 0,114·B (``cv2.COLOR_BGR2GRAY``)."""
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def gaussian_kernel_2d(ksize: int = GAUSSIAN_KSIZE, sigma: float = GAUSSIAN_SIGMA) -> np.ndarray:
    """Kernel gaussiano 2D (separável) usado na convolução — para documentação."""
    k1 = cv2.getGaussianKernel(ksize, sigma)
    return k1 @ k1.T


def spatial_filter(gray: np.ndarray) -> np.ndarray:
    """Filtragem espacial passa-baixa: convolução com kernel gaussiano 5x5 (σ=1,1).

    G(x, y) = (1 / 2πσ²) · exp(−(x² + y²) / 2σ²), normalizado para somar 1.
    Atenua o ruído do sensor e a granulação fina do pavimento sem apagar as
    bordas de regiões grandes (como a borda de um buraco).
    """
    return cv2.GaussianBlur(
        gray, (GAUSSIAN_KSIZE, GAUSSIAN_KSIZE), sigmaX=GAUSSIAN_SIGMA, sigmaY=GAUSSIAN_SIGMA,
        borderType=cv2.BORDER_REFLECT_101,
    )


def quality_metrics(gray: np.ndarray) -> dict:
    """Brilho, contraste, nitidez e distribuição do histograma da imagem em cinza.

    - brilho_medio: média dos níveis de cinza (0–255);
    - contraste_rms: desvio-padrão dos níveis de cinza;
    - nitidez_laplaciano: variância da resposta do Laplaciano (kernel 3x3
      [[0,1,0],[1,−4,1],[0,1,0]]) — imagens borradas têm poucas variações bruscas;
    - percentual de pixels muito escuros (≤ 20) e saturados (≥ 250);
    - histograma normalizado em 16 faixas.
    """
    g = gray.astype(np.float64)
    lap = cv2.Laplacian(gray, cv2.CV_64F, ksize=1)
    hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).ravel()
    hist = hist / max(1.0, hist.sum())
    n = float(gray.size)
    return {
        "brilho_medio": round(float(g.mean()), 2),
        "contraste_rms": round(float(g.std()), 2),
        "nitidez_laplaciano": round(float(lap.var()), 2),
        "percentual_pixels_escuros": round(100.0 * float(np.count_nonzero(gray <= 20)) / n, 2),
        "percentual_pixels_saturados": round(100.0 * float(np.count_nonzero(gray >= 250)) / n, 2),
        "histograma_16_faixas": [round(float(v), 4) for v in hist],
    }


def _br(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def quality_problems(q: dict) -> list[str]:
    """Lista (em português) os problemas de qualidade que impedem uma triagem confiável."""
    problems: list[str] = []
    if q["brilho_medio"] < QUALITY["brilho_minimo"] or q["percentual_pixels_escuros"] > QUALITY["escuros_maximo_pct"]:
        problems.append(
            f"Imagem muito escura (brilho médio {q['brilho_medio']:.0f} de 255; mínimo "
            f"{QUALITY['brilho_minimo']:.0f}). Fotografe com mais luz."
        )
    if q["brilho_medio"] > QUALITY["brilho_maximo"] or q["percentual_pixels_saturados"] > QUALITY["saturacao_maxima_pct"]:
        problems.append(
            f"Imagem muito clara ou estourada (brilho médio {q['brilho_medio']:.0f} de 255; "
            f"{q['percentual_pixels_saturados']:.0f}% de pixels saturados)."
        )
    if q["contraste_rms"] < QUALITY["contraste_minimo"]:
        problems.append(
            f"Contraste muito baixo (desvio-padrão {_br(q['contraste_rms'])}; mínimo "
            f"{QUALITY['contraste_minimo']:.0f}). Detalhes do piso não podem ser separados."
        )
    if q["nitidez_laplaciano"] < QUALITY["nitidez_minima"]:
        problems.append(
            f"Imagem borrada ou fora de foco (variância do Laplaciano {_br(q['nitidez_laplaciano'])}; "
            f"mínimo {QUALITY['nitidez_minima']:.0f}). Segure o celular firme e foque o piso."
        )
    return problems


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """Realce local de contraste com CLAHE (equalização adaptativa limitada).

    A imagem é dividida em 4x4 blocos; em cada bloco o histograma é equalizado com
    o limite de recorte 2,0 (evita amplificar ruído) e os blocos são unidos por
    interpolação bilinear.
    """
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    return clahe.apply(gray)


def order_points(pts: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos como superior-esquerdo, superior-direito, inferior-direito, inferior-esquerdo."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype=np.float32,
    )


def correct_perspective(
    img: np.ndarray, points, output_size: tuple[int, int] | None = None
) -> np.ndarray:
    """Transformação de perspectiva (homografia) a partir de 4 pontos do piso.

    Uso opcional: quando o cidadão (ou a equipe na revisão) marca os 4 cantos de um
    trecho retangular da calçada, a função "retifica" a vista oblíqua para uma vista
    de cima. Isso torna comparáveis as medidas de área/forma entre fotos.

    Matemática: resolve a matriz 3x3 H (``cv2.getPerspectiveTransform``) tal que
    [x', y', w']ᵀ = H · [x, y, 1]ᵀ e aplica (x'/w', y'/w') a cada pixel
    (``cv2.warpPerspective``, interpolação bilinear).

    Não faz parte do fluxo automático porque exige 4 pontos confiáveis, que a
    triagem automática não tem como obter com segurança em fotos arbitrárias.
    """
    try:
        src = order_points(np.asarray(points, dtype=np.float32))
    except Exception as exc:
        raise VisionError("INVALID_POINTS", "Informe exatamente 4 pontos (x, y) para corrigir a perspectiva.") from exc
    tl, tr, br, bl = src
    if output_size is None:
        width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    else:
        width, height = int(output_size[0]), int(output_size[1])
    if width < 16 or height < 16:
        raise VisionError("INVALID_POINTS", "Os 4 pontos informados delimitam uma área pequena demais.")
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, matrix, (width, height), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)
