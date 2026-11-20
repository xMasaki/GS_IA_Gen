"""Validação e decodificação segura de imagens.

A validação NÃO confia na extensão do arquivo nem no ``Content-Type``:
1. confere a assinatura binária (JPEG, PNG ou WEBP);
2. lê as dimensões declaradas no cabeçalho (antes de decodificar, para recusar
   "bombas de descompressão" com dimensões gigantes);
3. decodifica de verdade com ``cv2.imdecode`` e confere as dimensões reais.
"""

from __future__ import annotations

import struct

import cv2
import numpy as np

from .constants import MAX_DIMENSION, MIN_DIMENSION
from .errors import VisionError

SUPPORTED_FORMATS = ("JPEG", "PNG", "WEBP")


def detect_format(data: bytes) -> str | None:
    """Identifica o formato pela assinatura binária (magic bytes)."""
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    return None


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    i, n = 2, len(data)
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:  # preenchimento
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xD9 or marker == 0xDA:  # fim / início dos dados comprimidos
            return None
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in sof and i + 9 <= n:
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return int(w), int(h)
        i += 2 + seg_len
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    try:
        if chunk == b"VP8X" and len(data) >= 30:
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return w, h
        if chunk == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            return int(w & 0x3FFF), int(h & 0x3FFF)
        if chunk == b"VP8L" and len(data) >= 25:
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return w, h
    except Exception:  # pragma: no cover - cabeçalho corrompido
        return None
    return None


def header_size(data: bytes, fmt: str) -> tuple[int, int] | None:
    """Dimensões (largura, altura) declaradas no cabeçalho, quando legíveis."""
    if fmt == "PNG":
        return _png_size(data)
    if fmt == "JPEG":
        return _jpeg_size(data)
    if fmt == "WEBP":
        return _webp_size(data)
    return None


def _check_dimensions(width: int, height: int) -> None:
    if min(width, height) < MIN_DIMENSION:
        raise VisionError(
            "IMAGE_TOO_SMALL",
            f"A imagem é pequena demais ({width}x{height} px). "
            f"Envie uma fotografia com pelo menos {MIN_DIMENSION} px em cada lado.",
        )
    if max(width, height) > MAX_DIMENSION:
        raise VisionError(
            "IMAGE_DIMENSIONS_TOO_LARGE",
            f"A imagem tem dimensões grandes demais ({width}x{height} px). "
            f"O limite é {MAX_DIMENSION} px no maior lado.",
        )


def _check_bytes(data: bytes, max_bytes: int | None) -> str:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise VisionError("INVALID_INPUT", "O conteúdo enviado não é um arquivo de imagem.")
    data = bytes(data)
    if len(data) == 0:
        raise VisionError("EMPTY_IMAGE", "Nenhuma imagem foi enviada (arquivo vazio).")
    if max_bytes is not None and max_bytes > 0 and len(data) > max_bytes:
        limite_mb = max_bytes / (1024 * 1024)
        raise VisionError(
            "FILE_TOO_LARGE",
            f"A fotografia ultrapassa o tamanho máximo permitido ({limite_mb:.1f} MB).",
        )
    fmt = detect_format(data)
    if fmt is None:
        raise VisionError(
            "UNSUPPORTED_FORMAT",
            "Formato não suportado. Envie uma fotografia JPEG, PNG ou WEBP.",
        )
    size = header_size(data, fmt)
    if size is not None:
        _check_dimensions(*size)
    return fmt


def decode_image(data: bytes, max_bytes: int | None = None) -> np.ndarray:
    """Valida e decodifica a imagem, devolvendo uma matriz BGR uint8 (H, W, 3).

    ``cv2.IMREAD_COLOR`` aplica a orientação EXIF (a foto fica "em pé") e converte
    imagens em tons de cinza, com transparência ou 16 bits para BGR de 8 bits.
    """
    _check_bytes(data, max_bytes)
    buf = np.frombuffer(bytes(data), dtype=np.uint8)
    try:
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except cv2.error:
        img = None
    if img is None or img.size == 0:
        raise VisionError(
            "INVALID_IMAGE",
            "Não foi possível ler a imagem. O arquivo pode estar corrompido ou não ser uma fotografia.",
        )
    h, w = img.shape[:2]
    _check_dimensions(w, h)
    if img.dtype != np.uint8:  # pragma: no cover - IMREAD_COLOR já converte
        img = cv2.convertScaleAbs(img)
    return img


def validate_image_bytes(data: bytes, max_bytes: int) -> None:
    """Valida os bytes de uma fotografia enviada.

    Levanta :class:`VisionError` (com mensagem em português) quando:
    - o arquivo está vazio ou excede ``max_bytes``;
    - a assinatura não é JPEG, PNG ou WEBP;
    - a decodificação real falha (arquivo corrompido ou que não é imagem);
    - a imagem tem menos de 64 px ou mais de 8000 px em algum lado.
    """
    decode_image(data, max_bytes)
