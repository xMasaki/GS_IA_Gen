"""Fluxo completo da triagem: bytes da foto → classificação explicável + imagens das etapas.

Etapas (ver ``STAGE_ORDER``):
    original  → cópia de trabalho (maior lado 800 px) da foto recebida
    cinza     → conversão para luminância
    filtrada  → convolução gaussiana 5x5 (σ=1,1)
    contraste → CLAHE (realce local de contraste)
    bordas    → Canny sobre a imagem realçada
    mascara   → limiarização das regiões escuras (Otsu + limiar robusto) + morfologia
    contornos → contornos, caixas delimitadoras e rótulos desenhados sobre a original
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import classifier, features, preprocessing, segmentation
from .constants import (
    ALGORITHM_VERSION,
    AVISO,
    CLASS_LABELS,
    CLASSIFIER,
    DEFAULT_MAX_BYTES,
    GAUSSIAN_KSIZE,
    GAUSSIAN_SIGMA,
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_GRID,
    INCONCLUSIVE,
    POSSIBLE_POTHOLE,
    SEGMENTATION,
    SEGMENTATION_SIGMA,
    STAGE_ORDER,
    WORK_MAX_SIDE,
)
from .errors import VisionError
from .validation import decode_image
from .visualize import draw_contours_stage


@dataclass
class AnalysisResult:
    classification: str
    label: str
    score: float
    reasons: list[str]
    metrics: dict
    detections: list[dict]
    stages: dict[str, np.ndarray] = field(repr=False)
    algorithm_version: str = ALGORITHM_VERSION

    def to_dict(self) -> dict:
        """Tudo menos ``stages``, com chaves em português (contrato, seção 5)."""
        return {
            "classificacao": self.classification,
            "rotulo": self.label,
            "pontuacao": float(self.score),
            "explicacao": list(self.reasons),
            "metricas": self.metrics,
            "deteccoes": list(self.detections),
            "versao_algoritmo": self.algorithm_version,
            "aviso": AVISO,
        }

    def encode_stages(self, ext: str = ".jpg", quality: int = 85) -> dict[str, bytes]:
        """Codifica cada etapa (na ordem de ``STAGE_ORDER``) como bytes de imagem."""
        ext = ext if ext.startswith(".") else "." + ext
        params: list[int] = []
        if ext.lower() in (".jpg", ".jpeg"):
            params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        elif ext.lower() == ".webp":
            params = [int(cv2.IMWRITE_WEBP_QUALITY), int(quality)]
        out: dict[str, bytes] = {}
        for name in STAGE_ORDER:
            ok, buf = cv2.imencode(ext, self.stages[name], params)
            if not ok:  # pragma: no cover
                raise VisionError("ENCODE_FAILED", f"Não foi possível gerar a imagem da etapa '{name}'.")
            out[name] = buf.tobytes()
        return out


def _parameters() -> dict:
    return {
        "maior_lado_analise_px": WORK_MAX_SIDE,
        "filtro": f"GaussianBlur {GAUSSIAN_KSIZE}x{GAUSSIAN_KSIZE}, sigma={GAUSSIAN_SIGMA}",
        "clahe": f"clipLimit={CLAHE_CLIP_LIMIT}, tileGridSize={CLAHE_TILE_GRID[0]}x{CLAHE_TILE_GRID[1]}",
        "canny": f"{SEGMENTATION['canny_baixo']}/{SEGMENTATION['canny_alto']} (L2)",
        "morfologia": (
            f"abertura elipse {SEGMENTATION['abertura_kernel']}x{SEGMENTATION['abertura_kernel']} "
            f"x{SEGMENTATION['abertura_iteracoes']}; fechamento elipse "
            f"{SEGMENTATION['fechamento_kernel']}x{SEGMENTATION['fechamento_kernel']}; preenchimento de furos"
        ),
        "limiar_possivel_buraco": CLASSIFIER["limiar_possivel_buraco"],
        "limiar_inconclusivo": CLASSIFIER["limiar_inconclusivo"],
    }


def analyze_array(img_bgr: np.ndarray, *, original_size: tuple[int, int] | None = None) -> AnalysisResult:
    """Analisa uma imagem BGR já decodificada."""
    h0, w0 = img_bgr.shape[:2]
    if original_size is not None:
        w0, h0 = original_size
    work, _ = preprocessing.resize_for_analysis(img_bgr)
    h, w = work.shape[:2]

    gray = preprocessing.to_gray(work)
    filtered = preprocessing.spatial_filter(gray)
    quality = preprocessing.quality_metrics(gray)
    problems = preprocessing.quality_problems(quality)
    contrast = preprocessing.enhance_contrast(filtered)

    edges = segmentation.detect_edges(contrast)
    # A limiarização usa uma versão mais suavizada (σ = 3) da imagem em cinza: apaga a
    # granulação do piso (que fragmentaria a máscara) e preserva as formas grandes. O CLAHE
    # altera o nível de cinza de regiões grandes e é usado só para as bordas (Canny).
    seg_gray = cv2.GaussianBlur(gray, (0, 0), SEGMENTATION_SIGMA)
    thr, levels = segmentation.threshold_levels(seg_gray)

    ctx = features.prepare_context(gray, filtered, edges)
    global_edges = ctx["global_edge_density"]

    # Multi-limiar: cada nível gera uma máscara (limiar → morfologia → contornos); as
    # candidatas de todos os níveis são medidas e pontuadas pela mesma regra.
    candidates: list[dict] = []
    level_masks: list[np.ndarray] = []
    level_contours: list[list[np.ndarray]] = []
    for li, lv in enumerate(levels):
        lmask = segmentation.morphology(segmentation.threshold_dark(seg_gray, lv["valor"]))
        level_masks.append(lmask)
        level_contours.append(segmentation.find_candidate_contours(lmask))
        for cnt in level_contours[-1]:
            f = features.contour_features(cnt, ctx)
            score, subs = classifier.score_candidate(f)
            f["pontuacao"] = score
            f["subpontuacoes"] = subs
            f["criterios_nao_atendidos"] = classifier.gate_failures(f)
            f["nivel_limiar"] = lv["nome"]
            f["limiar"] = lv["valor"]
            f["_nivel_idx"] = li
            f["_contorno"] = cnt
            candidates.append(f)
    candidates = classifier.merge_candidates(candidates)
    classifier.annotate_stability(candidates, len(levels))

    chosen = classifier.pick_level(candidates)
    mask = level_masks[chosen]
    thr["limiar_aplicado"] = levels[chosen]["valor"]
    mask_pct = 100.0 * float(np.count_nonzero(mask)) / float(mask.size)
    contours = [cd.pop("_contorno") for cd in candidates]
    for cd in candidates:
        cd.pop("_nivel_idx", None)

    decision = classifier.classify(problems, candidates, mask_pct)
    cls = decision["classification"]
    score = float(decision["score"])

    # detecções: candidatas válidas acima do limiar de suspeita (não há detecções se a foto é inadequada)
    det_idx: set[int] = set()
    if not problems:
        for i, cd in enumerate(candidates):
            if cd["criterios_nao_atendidos"]:
                continue
            if cls == POSSIBLE_POTHOLE and cd["pontuacao"] >= CLASSIFIER["limiar_possivel_buraco"]:
                det_idx.add(i)
            elif cls == INCONCLUSIVE and cd["pontuacao"] >= CLASSIFIER["limiar_inconclusivo"]:
                det_idx.add(i)
    detections = []
    for i in sorted(det_idx, key=lambda k: -candidates[k]["pontuacao"]):
        cd = candidates[i]
        detections.append({
            "x": cd["x"], "y": cd["y"], "largura": cd["largura"], "altura": cd["altura"],
            "area_px": cd["area_px"], "area_relativa": cd["area_relativa"],
            "pontuacao": cd["pontuacao"],
            "tipo": "possivel_buraco" if cls == POSSIBLE_POTHOLE else "regiao_suspeita",
        })

    contour_img = draw_contours_stage(
        work, contours, candidates, det_idx, cls, score, suspect=(cls == INCONCLUSIVE)
    )

    metrics = {
        "largura_original": int(w0),
        "altura_original": int(h0),
        "largura_analise": int(w),
        "altura_analise": int(h),
        **quality,
        "qualidade_adequada": not problems,
        "problemas_qualidade": problems,
        **thr,
        "percentual_mascara": round(mask_pct, 2),
        "densidade_bordas_global": round(global_edges, 4),
        "num_candidatas": len(candidates),
        "num_deteccoes": len(detections),
        "decisao": decision["decisao"],
        "candidatas": candidates,
        "parametros": _parameters(),
        "coordenadas_referem_se_a": "imagem de análise (largura_analise x altura_analise)",
    }

    stages = {
        "original": work,
        "cinza": gray,
        "filtrada": filtered,
        "contraste": contrast,
        "bordas": edges,
        "mascara": mask,
        "contornos": contour_img,
    }
    return AnalysisResult(
        classification=cls,
        label=CLASS_LABELS[cls],
        score=round(score, 4),
        reasons=decision["reasons"],
        metrics=metrics,
        detections=detections,
        stages=stages,
    )


def analyze_image(data: bytes, *, perspective_points=None) -> AnalysisResult:
    """Valida, decodifica e analisa uma fotografia.

    ``perspective_points`` (opcional): 4 pontos (x, y) na imagem original delimitando um
    trecho retangular do piso; se informados, a imagem é retificada antes da análise.

    Levanta :class:`VisionError` para entradas inválidas.
    """
    img = decode_image(data, DEFAULT_MAX_BYTES)
    h0, w0 = img.shape[:2]
    if perspective_points is not None:
        img = preprocessing.correct_perspective(img, perspective_points)
    return analyze_array(img, original_size=(w0, h0))
