"""画像セッション状態（原画像/マスク/パラメータ/レビュー状態）。

フル解像度の画素はすべてここ（Python 側）に保持する。ブリッジには流さない（仕様 §3.3）。
"""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class ImageItem:
    id: str
    path: str
    name: str
    original: np.ndarray            # 原画像 BGR（フル解像度）
    h: int
    w: int
    model_mask: Optional[np.ndarray] = None   # 検出マスク 0/255（原寸）
    add_mask: Optional[np.ndarray] = None     # ユーザ追加（原寸 0/255）
    remove_mask: Optional[np.ndarray] = None  # ユーザ削除（原寸 0/255）
    block_px: Optional[int] = None            # モザイク強度（None=config 既定）
    reviewed: bool = False
    detected: bool = False

    def status(self) -> str:
        if self.reviewed:
            return "reviewed"
        if self.detected:
            return "detected"
        return "none"

    def final_mask(self) -> np.ndarray:
        """(model_mask OR add) AND NOT remove を 0/255 で返す（grow/blur 前）。"""
        base = self.model_mask if self.model_mask is not None else \
            np.zeros((self.h, self.w), np.uint8)
        m = base.copy()
        if self.add_mask is not None:
            m = np.maximum(m, self.add_mask)
        if self.remove_mask is not None:
            m[self.remove_mask > 0] = 0
        return m


class Session:
    """取り込み中の全画像を管理するスレッドセーフなストア。"""

    def __init__(self):
        self._items: Dict[str, ImageItem] = {}
        self._lock = threading.Lock()

    def add(self, path: str, image: np.ndarray) -> ImageItem:
        h, w = image.shape[:2]
        item = ImageItem(
            id=uuid.uuid4().hex[:12],
            path=path,
            name=os.path.basename(path),
            original=image,
            h=h, w=w,
        )
        with self._lock:
            self._items[item.id] = item
        return item

    def get(self, item_id: str) -> Optional[ImageItem]:
        with self._lock:
            return self._items.get(item_id)

    def all(self) -> List[ImageItem]:
        with self._lock:
            return list(self._items.values())

    def ids(self) -> List[str]:
        with self._lock:
            return list(self._items.keys())

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def reviewed_count(self) -> int:
        with self._lock:
            return sum(1 for it in self._items.values() if it.reviewed)
