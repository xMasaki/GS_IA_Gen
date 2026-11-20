"""Privacidade (LGPD) aplicada à fotografia antes de qualquer armazenamento.

``sanitize_image``:
1. valida e decodifica a imagem (a orientação EXIF é aplicada aos pixels);
2. reduz a imagem para que o maior lado tenha no máximo ``max_side`` px;
3. detecta rostos frontais com o classificador Haar que acompanha o OpenCV
   (``cv2.data.haarcascades``) e os borra com um filtro gaussiano forte;
4. recodifica em JPEG **sem** copiar metadados — EXIF, GPS, modelo do aparelho,
   data/hora e miniaturas são descartados, pois o JPEG é gerado a partir dos pixels.

Se o arquivo do classificador Haar não estiver disponível, a função continua sem
falhar e registra um aviso no log (``logging``) e no relatório de
``sanitize_image_with_report``.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import cv2
import numpy as np

from .errors import VisionError
from .validation import decode_image

logger = logging.getLogger("acessacidade_vision.privacy")

JPEG_QUALITY = 90
FACE_CASCADE_FILE = "haarcascade_frontalface_default.xml"


@lru_cache(maxsize=1)
def _load_face_cascade():
    """Carrega o classificador Haar de rostos; devolve ``None`` se indisponível."""
    try:
        base = getattr(cv2, "data", None)
        path = os.path.join(base.haarcascades, FACE_CASCADE_FILE) if base else ""
        if not path or not os.path.exists(path):
            logger.warning("Classificador Haar de rostos não encontrado; rostos não serão borrados.")
            return None
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            logger.warning("Classificador Haar de rostos vazio; rostos não serão borrados.")
            return None
        return cascade
    except Exception:  # pragma: no cover - ambiente sem dados do OpenCV
        logger.warning("Falha ao carregar o classificador Haar; rostos não serão borrados.")
        return None


def resize_max_side(img: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """Reduz (nunca amplia) a imagem para que o maior lado tenha ``max_side`` px."""
    h, w = img.shape[:2]
    if max_side is None or max_side <= 0 or max(h, w) <= max_side:
        return img, 1.0
    scale = max_side / float(max(h, w))
    new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA), scale


ACHROMATIC_LIMIT = 10.0  # croma média (|Cr−128| + |Cb−128|) abaixo disto = região sem cor
COLOR_IMAGE_LIMIT = 1.0  # croma média da foto inteira acima disto = foto colorida (não monocromática)


def _chroma(img_bgr: np.ndarray) -> float:
    ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    return float(np.mean(np.abs(ycrcb[..., 1] - 128.0) + np.abs(ycrcb[..., 2] - 128.0)))


def detect_faces(img: np.ndarray) -> list[tuple[int, int, int, int]] | None:
    """Detecta rostos frontais. Devolve ``None`` se o classificador não estiver disponível.

    O classificador Haar gera falsos positivos em texturas de pavimento. Numa foto
    COLORIDA, uma detecção praticamente sem cor (cinza de concreto/asfalto) é
    descartada, pois pele humana sempre tem croma. Em fotos em tons de cinza nenhuma
    detecção é descartada (a privacidade tem prioridade sobre o detalhe da imagem).
    """
    cascade = _load_face_cascade()
    if cascade is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    min_side = max(24, int(min(gray.shape[:2]) * 0.05))
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side)
    )
    boxes = [tuple(int(v) for v in f) for f in faces] if len(faces) else []
    if boxes and _chroma(img) > COLOR_IMAGE_LIMIT:
        boxes = [b for b in boxes if _chroma(img[b[1]:b[1] + b[3], b[0]:b[0] + b[2]]) >= ACHROMATIC_LIMIT]
    return boxes


def blur_regions(img: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    """Borra (gaussiano forte) cada retângulo, com margem de 20%."""
    out = img.copy()
    h, w = out.shape[:2]
    for (x, y, bw, bh) in boxes:
        mx, my = int(bw * 0.2), int(bh * 0.2)
        x0, y0 = max(0, x - mx), max(0, y - my)
        x1, y1 = min(w, x + bw + mx), min(h, y + bh + my)
        roi = out[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        k = max(15, (max(roi.shape[:2]) // 3) | 1)  # kernel ímpar proporcional ao rosto
        out[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)
    return out


def sanitize_image_with_report(
    data: bytes, *, max_side: int = 1600, blur_faces: bool = True, max_bytes: int | None = None
) -> tuple[bytes, dict]:
    """Igual a :func:`sanitize_image`, mas devolve também um relatório do que foi feito."""
    img = decode_image(data, max_bytes)
    h0, w0 = img.shape[:2]
    img, scale = resize_max_side(img, max_side)
    report = {
        "largura_original": int(w0),
        "altura_original": int(h0),
        "largura_final": int(img.shape[1]),
        "altura_final": int(img.shape[0]),
        "redimensionada": scale < 1.0,
        "metadados_removidos": True,
        "rostos_borrados": 0,
        "detector_rostos_disponivel": None,
    }
    if blur_faces:
        faces = detect_faces(img)
        if faces is None:
            report["detector_rostos_disponivel"] = False
        else:
            report["detector_rostos_disponivel"] = True
            if faces:
                img = blur_regions(img, faces)
                report["rostos_borrados"] = len(faces)
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:  # pragma: no cover - falha improvável do codificador
        raise VisionError("ENCODE_FAILED", "Não foi possível preparar a imagem para armazenamento.")
    return enc.tobytes(), report


def sanitize_image(data: bytes, *, max_side: int = 1600, blur_faces: bool = True) -> bytes:
    """Remove metadados (EXIF/GPS), reduz a resolução e borra rostos.

    Devolve sempre bytes JPEG gerados a partir dos pixels (nenhum metadado do
    arquivo original é copiado). Levanta :class:`VisionError` para entradas inválidas.
    """
    out, _ = sanitize_image_with_report(data, max_side=max_side, blur_faces=blur_faces)
    return out
