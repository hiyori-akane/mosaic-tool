"""検出エンジン（差し替え可能な共通インターフェース）。

現状は ultralytics YOLO segmentation の ``engine_yolo`` を提供する。
別バックエンドを追加する場合は ``DetectorEngine`` を実装し、
``get_engine`` に分岐を足すこと。
"""

from __future__ import annotations

from typing import Optional

from .base import Detection, DetectorEngine

__all__ = ["Detection", "DetectorEngine", "get_engine"]


def get_engine(name: str = "yolo", model_path: Optional[str] = None,
               **kwargs) -> DetectorEngine:
    """エンジン名から DetectorEngine を生成するファクトリ。

    name="yolo" : ultralytics YOLO segmentation エンジン。
    """
    name = (name or "yolo").lower()
    if name == "yolo":
        from .engine_yolo import YoloEngine
        return YoloEngine(model_path, **kwargs)
    raise ValueError(f"unknown engine: {name!r} (expected 'yolo')")
