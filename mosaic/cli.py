"""バッチ/単体実行の CLI エントリ。

例:
  python -m mosaic.cli ./in -o ./out --model models/ntd11_anime_nsfw_segm_v5.pt
"""

from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

from .config import load_config
from .engines import get_engine
from .mask_ops import build_mask
from .mosaic import mosaic_image

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _imread(path: str):
    """マルチバイトパス対応の読み込み（Windows の非ASCIIパス対策）。失敗時 None。"""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _imwrite(path: str, img) -> bool:
    """マルチバイトパス対応の書き出し。"""
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    try:
        buf.tofile(path)
    except OSError:
        return False
    return True


def process(engine, cfg, path_in: str, path_out: str) -> None:
    img = _imread(path_in)
    if img is None:
        print(f"  skip (読み込み不可): {path_in}")
        return
    h, w = img.shape[:2]
    detections = engine.infer(img)
    mask = build_mask(detections, h, w, cfg)
    out = mosaic_image(img, mask, cfg)
    if not _imwrite(path_out, out):
        print(f"  書き出し失敗: {path_out}", file=sys.stderr)
        return
    tag = "完了" if int(mask.max()) else "検出なし→コピー"
    print(f"  {tag}: {os.path.basename(path_in)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="auto-mosaic (YOLO)")
    ap.add_argument("input", help="画像ファイル または フォルダ")
    ap.add_argument("-o", "--output", default="out", help="出力フォルダ (既定: ./out)")
    ap.add_argument("--model", default=None, help="YOLO モデルのパス (.pt)")
    ap.add_argument("--engine", default="yolo", choices=["yolo"],
                    help="検出エンジン (既定: yolo)")
    ap.add_argument("--device", default=None,
                    help="推論デバイス（例: cpu / mps / cuda）。既定: 自動")
    ap.add_argument("--config", default=None, help="config.yaml のパス")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    try:
        engine = get_engine(args.engine, args.model, device=args.device)
    except Exception as e:  # noqa: BLE001
        print(f"エンジン初期化に失敗: {e}", file=sys.stderr)
        return 2

    os.makedirs(args.output, exist_ok=True)
    if os.path.isdir(args.input):
        files = sorted(f for f in os.listdir(args.input)
                       if f.lower().endswith(IMG_EXTS))
        print(f"{len(files)} 枚を処理します")
        for f in files:
            try:
                process(engine, cfg, os.path.join(args.input, f),
                        os.path.join(args.output, f))
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:  # noqa: BLE001 — 1枚の失敗でバッチ全体を止めない
                print(f"  error ({f}): {e}", file=sys.stderr)
    else:
        process(engine, cfg, args.input,
                os.path.join(args.output, os.path.basename(args.input)))
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
