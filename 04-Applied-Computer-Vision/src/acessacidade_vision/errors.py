"""Erro padrão do pacote de visão computacional."""

from __future__ import annotations


class VisionError(Exception):
    """Erro de validação/processamento de imagem.

    Atributos:
        code: código técnico estável (ex.: ``INVALID_IMAGE``), útil para logs e testes.
        message: mensagem em português, pronta para ser exibida ao cidadão.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"VisionError(code={self.code!r}, message={self.message!r})"
