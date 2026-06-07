"""検出エンジンの共通インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Detection:
    """1 件の検出結果（バックエンド非依存の正規化表現）。

    mask  : インスタンスマスク。任意サイズの float/bool/uint8（>0.5 を前景とみなす）。
    cls   : クラス名（文字列）。config のグループ振り分けに使う。
    score : 信頼度 0-1。
    bbox  : (x1, y1, x2, y2) 原画像座標。
    """

    mask: np.ndarray
    cls: str
    score: float
    bbox: Tuple[float, float, float, float]


class DetectorEngine(ABC):
    """検出エンジン抽象基底。"""

    @abstractmethod
    def infer(self, image_bgr: np.ndarray) -> List[Detection]:
        """BGR 画像を受け取り Detection のリストを返す。"""
        raise NotImplementedError
