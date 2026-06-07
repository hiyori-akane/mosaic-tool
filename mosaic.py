#!/usr/bin/env python3
"""後方互換シム。

旧 `python mosaic.py <in> -o <out>` は、コア `mosaic/cli.py`（YOLO）へ転送する。
既存の .pt をそのまま使える。マスク後処理・モザイクのロジックは `mosaic/`
パッケージに集約済み。

新しい使い方:
  python -m mosaic.cli <in> -o <out> --model models/x.pt
"""

import os
import sys

# `mosaic` パッケージ（同名ディレクトリ）を確実に解決するため親をパスへ
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from mosaic.cli import main

    argv = sys.argv[1:]

    def _has(flag):
        # "--flag" と "--flag=value" の両形に対応
        return any(a == flag or a.startswith(flag + "=") for a in argv)

    # モデル未指定時は既定の .pt を補う。明示指定があれば尊重。
    if not _has("--model"):
        default_pt = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "models", "ntd11_anime_nsfw_segm_v5.pt")
        argv += ["--model", default_pt]
    raise SystemExit(main(argv))
