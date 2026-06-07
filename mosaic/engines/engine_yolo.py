"""ultralytics YOLO セグメンテーションの DetectorEngine 実装。

既存の ``ntd11_anime_nsfw_segm_v5.pt`` などの YOLO segmentation モデルで
GUI / CLI を動作させる検出エンジン。
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from .base import Detection, DetectorEngine


class YoloEngine(DetectorEngine):
    def __init__(self, model_path: Optional[str], device: Optional[str] = None,
                 conf: float = 0.01, **kwargs):
        if not model_path:
            raise FileNotFoundError("YOLO モデル(.pt)のパスを指定してください。")
        from ultralytics import YOLO  # 遅延 import（起動を軽くする）
        self.model = YOLO(model_path)
        self.names = self.model.names
        self.device = device
        self.conf = conf

    def infer(self, image_bgr: np.ndarray) -> List[Detection]:
        kw = {} if self.device is None else {"device": self.device}
        result = self.model(image_bgr, conf=self.conf, retina_masks=True,
                            verbose=False, **kw)[0]
        out: List[Detection] = []
        if result.masks is None or result.boxes is None:
            return out

        masks = result.masks.data.cpu().numpy()
        cls = result.boxes.cls.cpu().numpy().astype(int)
        conf = result.boxes.conf.cpu().numpy()
        boxes = result.boxes.xyxy.cpu().numpy()

        # zip(strict=) は 3.10+。古い Python でも動くよう既定の zip を使う
        # （YOLO 出力は各配列の長さが一致している前提）。
        for m, c, cf, box in zip(masks, cls, conf, boxes):
            out.append(Detection(
                mask=m.astype(np.float32),
                cls=str(self.names[c]),
                score=float(cf),
                bbox=tuple(float(v) for v in box),
            ))
        return out
