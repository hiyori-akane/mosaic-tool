"""新コア（mosaic/）が旧 PoC mosaic.py のロジックと一致することを検証する。

旧実装のロジックを参照実装として本ファイルに再現し、同一入力で画素一致を確認。
"""

import cv2
import numpy as np

from mosaic.config import load_config
from mosaic.engines.base import Detection
from mosaic.mask_ops import build_mask
from mosaic.mosaic import apply_mosaic

# ---- 旧 mosaic.py の定数（PoC 既定値） -------------------------------------
GENITAL_CLASSES = {"pussy", "anus", "penis", "testicles", "x-ray", "cross-section"}
GENITAL_CONF, GENITAL_DILATE = 0.50, 2
NIPPLE_CLASSES = {"nipples"}
NIPPLE_CONF, NIPPLE_DILATE, NIPPLE_GROW = 0.01, 50, 10
OVERALL_GROW, BLUR_SIGMA, DROP_SIZE = 2, 10, 10
MOSAIC_PIXELS = 10


def _ellipse(px):
    px = max(1, int(round(px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px * 2 + 1, px * 2 + 1))


def _expand(mask, px):
    return cv2.dilate(mask, _ellipse(px)) if px and px > 0 else mask


def _legacy_build_mask(dets, h, w):
    """旧 mosaic.py build_mask の忠実な再現。"""
    genital = np.zeros((h, w), np.uint8)
    nipple = np.zeros((h, w), np.uint8)
    for d in dets:
        x1, y1, x2, y2 = d.bbox
        if min(x2 - x1, y2 - y1) < DROP_SIZE:
            continue
        seg = cv2.resize(d.mask.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
        seg = (seg > 0.5).astype(np.uint8) * 255
        name = d.cls.lower()
        if name in GENITAL_CLASSES and d.score >= GENITAL_CONF:
            genital = cv2.bitwise_or(genital, _expand(seg, GENITAL_DILATE))
        elif name in NIPPLE_CLASSES and d.score >= NIPPLE_CONF:
            nipple = cv2.bitwise_or(nipple, _expand(seg, NIPPLE_DILATE))
    nipple = _expand(nipple, NIPPLE_GROW)
    combined = cv2.bitwise_or(genital, nipple)
    combined = _expand(combined, OVERALL_GROW)
    k = int(BLUR_SIGMA * 4) | 1
    return cv2.GaussianBlur(combined, (k, k), float(BLUR_SIGMA))


def _legacy_mosaic(img, block):
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // block), max(1, h // block)),
                       interpolation=cv2.INTER_LANCZOS4)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def _sample_detections(h, w):
    g = np.zeros((h, w), np.float32)
    g[100:180, 120:200] = 1.0
    n = np.zeros((h, w), np.float32)
    n[40:70, 300:330] = 1.0
    return [
        Detection(mask=g, cls="pussy", score=0.8, bbox=(120, 100, 200, 180)),
        # 旧定数では "nipples"（複数形）。config 既定は両方を nipple グループに含む。
        Detection(mask=n, cls="nipples", score=0.05, bbox=(300, 40, 330, 70)),
    ]


def test_build_mask_parity():
    h, w = 256, 384
    dets = _sample_detections(h, w)
    cfg = load_config()
    new = build_mask(dets, h, w, cfg)
    legacy = _legacy_build_mask(dets, h, w)
    assert new.shape == legacy.shape
    assert np.array_equal(new, legacy), "build_mask が旧ロジックと不一致"


def test_mosaic_parity():
    img = (np.random.RandomState(0).rand(256, 384, 3) * 255).astype(np.uint8)
    new = apply_mosaic(img, MOSAIC_PIXELS)
    legacy = _legacy_mosaic(img, MOSAIC_PIXELS)
    assert np.array_equal(new, legacy), "apply_mosaic が旧ロジックと不一致"
