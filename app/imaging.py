"""画像 <-> dataURL 変換と表示解像度リサイズ（ブリッジ往復ヘルパ）。

仕様 §8 の往復設計を支える小道具。ブリッジに流すのは表示解像度の dataURL のみ。
"""

from __future__ import annotations

import base64
import os
from typing import Tuple

import cv2
import numpy as np

# 表示用に縮小する最大辺（フル解像度はブリッジに流さない）
DISPLAY_MAX_SIDE = 1280
THUMB_MAX_SIDE = 256


def display_scale(h: int, w: int, max_side: int = DISPLAY_MAX_SIDE) -> float:
    """原寸 -> 表示解像度の倍率（<=1.0）。"""
    longest = max(h, w)
    return min(1.0, max_side / longest) if longest > 0 else 1.0


def imread_unicode(path: str):
    """マルチバイトパス対応の画像読み込み（Windows の非ASCIIパス対策）。失敗時 None。

    cv2.imread は Windows で日本語等を含むパスを開けないため、np.fromfile +
    cv2.imdecode を使う。
    """
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, img_bgr: np.ndarray) -> bool:
    """マルチバイトパス対応の画像書き出し（Windows の非ASCIIパス対策）。"""
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img_bgr)
    if not ok:
        return False
    try:
        buf.tofile(path)
    except OSError:
        return False
    return True


def to_data_url(img_bgr: np.ndarray, fmt: str = ".png") -> str:
    """BGR 画像を data URL(PNG/JPEG) へ。"""
    ok, buf = cv2.imencode(fmt, img_bgr)
    if not ok:
        raise ValueError("画像エンコードに失敗しました")
    mime = "image/png" if fmt == ".png" else "image/jpeg"
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def mask_to_data_url(mask: np.ndarray) -> str:
    """単チャンネルマスク(0-255) を PNG data URL へ。"""
    return to_data_url(mask, ".png")


def data_url_to_image(data_url: str, grayscale: bool = False):
    """data URL を OpenCV 画像へデコード。失敗時 None。"""
    if not data_url:
        return None
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    arr = np.frombuffer(raw, np.uint8)
    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    return cv2.imdecode(arr, flag)


def resize_to_display(img_bgr: np.ndarray, max_side: int = DISPLAY_MAX_SIDE
                      ) -> Tuple[np.ndarray, float]:
    """表示解像度へ縮小した画像と倍率を返す。"""
    h, w = img_bgr.shape[:2]
    scale = display_scale(h, w, max_side)
    if scale >= 1.0:
        return img_bgr.copy(), 1.0
    dw, dh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    return cv2.resize(img_bgr, (dw, dh), interpolation=cv2.INTER_AREA), scale


def make_thumb(img_bgr: np.ndarray, max_side: int = THUMB_MAX_SIDE) -> str:
    """一覧用サムネイル data URL（JPEG）。"""
    thumb, _ = resize_to_display(img_bgr, max_side)
    return to_data_url(thumb, ".jpg")


def upscale_mask(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    """表示解像度のマスクを原寸 (h,w) の 0/255 uint8 へ。"""
    if mask is None:
        return np.zeros((h, w), np.uint8)
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    return (mask > 127).astype(np.uint8) * 255
