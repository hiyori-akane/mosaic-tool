"""モザイク生成とマスク合成（仕様 §6 ステップ 3-4）。"""

from __future__ import annotations

import cv2
import numpy as np

from .config import Config


def block_size(h: int, w: int, cfg: Config) -> int:
    """モザイクのブロックサイズ(px)を決定する。

    fixed     : config の block_px をそのまま使う。
    longside  : max(min_block_px, max(h, w) // longside_div)。
    """
    if cfg.mosaic.mode == "longside":
        return max(cfg.mosaic.min_block_px, max(h, w) // cfg.mosaic.longside_div)
    return max(1, cfg.mosaic.block_px)


def apply_mosaic(img: np.ndarray, block: int) -> np.ndarray:
    """ダウンスケール(lanczos) → ニアレスト拡大 で全面モザイク画像を作る。"""
    h, w = img.shape[:2]
    block = max(1, int(block))
    small = cv2.resize(
        img, (max(1, w // block), max(1, h // block)),
        interpolation=cv2.INTER_LANCZOS4,   # 縮小: lanczos
    )
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)  # 拡大: nearest


def blend(img: np.ndarray, mosaic: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """alpha(=ぼかし済みマスク 0-255) でモザイクを元画像に合成する。"""
    a = (mask.astype(np.float32) / 255.0)[..., None]
    return (img * (1.0 - a) + mosaic * a).astype(np.uint8)


def mosaic_image(img: np.ndarray, mask: np.ndarray, cfg: Config,
                 block: int | None = None) -> np.ndarray:
    """元画像 + 最終マスク → モザイク合成済み画像。

    block を指定すると config を上書き（GUI のモザイク強度スライダ用）。
    """
    h, w = img.shape[:2]
    if int(mask.max()) == 0:
        return img.copy()
    if block is None:
        block = block_size(h, w, cfg)
    return blend(img, apply_mosaic(img, block), mask)
