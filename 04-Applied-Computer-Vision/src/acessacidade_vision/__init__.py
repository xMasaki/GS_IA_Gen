"""AcessaCidade — triagem de fotografias de calçadas por visão computacional clássica (OpenCV).

Interface pública (contrato de integração, seção 5)::

    from acessacidade_vision import (
        analyze_image, sanitize_image, validate_image_bytes,
        AnalysisResult, VisionError, ALGORITHM_VERSION, STAGE_ORDER, CLASS_LABELS,
    )

A triagem é **apoio** à equipe: o resultado é uma pontuação heurística explicável,
não uma probabilidade, e sempre requer revisão humana.
"""

from .constants import ALGORITHM_VERSION, AVISO, CLASS_LABELS, STAGE_ORDER
from .errors import VisionError
from .pipeline import AnalysisResult, analyze_array, analyze_image
from .preprocessing import correct_perspective
from .privacy import sanitize_image, sanitize_image_with_report
from .validation import decode_image, validate_image_bytes

__all__ = [
    "analyze_image",
    "analyze_array",
    "sanitize_image",
    "sanitize_image_with_report",
    "validate_image_bytes",
    "decode_image",
    "correct_perspective",
    "AnalysisResult",
    "VisionError",
    "ALGORITHM_VERSION",
    "STAGE_ORDER",
    "CLASS_LABELS",
    "AVISO",
]

__version__ = ALGORITHM_VERSION
