"""マスク後処理（grow / blur / グループ別合成）。

仕様 §6 の厳密ロジックを、検出バックエンドに依存しない形で実装する。
入力は ``List[Detection]``（engines.base.Detection）。
既存 PoC ``mosaic.py`` と同一結果になるよう保つ（tests/test_parity.py で検証）。
"""

from __future__ import annotations

from typing import List

import cv2
import numpy as np

from .config import Config


def _ellipse(px: int):
    """楕円カーネル (2*px+1)。dilate 用。"""
    px = max(1, int(round(px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px * 2 + 1, px * 2 + 1))


def expand(mask: np.ndarray, px: int) -> np.ndarray:
    """マスクを px ピクセル膨張（GrowMask / dilation 相当）。"""
    if px and px > 0:
        return cv2.dilate(mask, _ellipse(px))
    return mask


def _to_seg(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    """検出マスク(任意サイズ float/bool/uint8)を (h,w) の 0/255 uint8 へ。"""
    m = mask.astype(np.float32)
    if m.shape[:2] != (h, w):
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
    return (m > 0.5).astype(np.uint8) * 255


def build_mask(detections: List, h: int, w: int, cfg: Config) -> np.ndarray:
    """検出結果から、ぼかし済みの最終モザイクマスク(uint8 0-255)を作る。

    仕様 §6:
      1) グループ別マスク構築（drop_size / conf / dilate）
      2) nipple grow → genital と OR → overall grow → GaussianBlur
    """
    genital = np.zeros((h, w), np.uint8)
    nipple = np.zeros((h, w), np.uint8)

    for det in detections:
        x1, y1, x2, y2 = det.bbox
        if min(x2 - x1, y2 - y1) < cfg.mask.drop_size_px:
            continue
        group = cfg.group_of(det.cls)
        if group is None:
            continue
        seg = _to_seg(det.mask, h, w)
        if group == "genital" and det.score >= cfg.genital.conf:
            genital = cv2.bitwise_or(genital, expand(seg, cfg.genital.dilate_px))
        elif group == "nipple" and det.score >= cfg.nipple.conf:
            nipple = cv2.bitwise_or(nipple, expand(seg, cfg.nipple.dilate_px))

    nipple = expand(nipple, cfg.nipple.grow_px)            # GrowMask (nipple)
    combined = cv2.bitwise_or(genital, nipple)             # MaskComposite "add"
    combined = expand(combined, cfg.mask.overall_grow_px)  # GrowMask (全体)
    return blur_mask(combined, cfg.mask.blur_sigma)


def blur_mask(mask: np.ndarray, sigma: float) -> np.ndarray:
    """ImpactGaussianBlurMask 相当。sigma に十分なカーネルを使う。"""
    if sigma and sigma > 0:
        k = int(sigma * 4) | 1
        return cv2.GaussianBlur(mask, (k, k), float(sigma))
    return mask
