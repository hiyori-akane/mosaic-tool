"""auto-mosaic コア（マスク後処理・モザイク・検出エンジン）。

GUI / CLI が共有するロジックを提供する。検出は ultralytics YOLO
（``mosaic.engines.engine_yolo``）、マスク後処理・モザイクは opencv / numpy。
"""

from .config import Config, load_config
from .mask_ops import blur_mask, build_mask, expand
from .mosaic import apply_mosaic, blend, block_size, mosaic_image

__all__ = [
    "Config",
    "load_config",
    "build_mask",
    "blur_mask",
    "expand",
    "apply_mosaic",
    "blend",
    "block_size",
    "mosaic_image",
]
