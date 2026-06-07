"""エントリポイント。pywebview ウィンドウを起動し js_api をブリッジする。

完全オフライン動作。models/ 配下の .pt（YOLO segmentation）を自動検出して
使用する。モデルが無ければ検出は無効で、手動補正のみ利用できる。
"""

from __future__ import annotations

import argparse
import os
import sys

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _model_search_dirs():
    """models/.pt を探索するディレクトリ群（優先順）。

    通常実行ではリポジトリ直下、PyInstaller 等でフリーズした配布物では
    実行ファイル隣／カレントディレクトリの models/ も見る（同梱しない
    モデルを利用者が置けるようにする）。
    """
    dirs = [os.path.join(ROOT, "models")]
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(os.path.dirname(sys.executable), "models"))
    dirs.append(os.path.join(os.getcwd(), "models"))
    # 重複を除いて順序を保つ
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _resolve_model(args):
    """使用する YOLO モデル(.pt)のパスを決定する。"""
    if args.model and os.path.exists(args.model):
        return args.model
    # 既定の探索: models/*.pt（順序を安定させるため sorted）
    for models_dir in _model_search_dirs():
        if os.path.isdir(models_dir):
            pt = sorted(f for f in os.listdir(models_dir) if f.endswith(".pt"))
            if pt:
                return os.path.join(models_dir, pt[0])
    return args.model


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="auto-mosaic デスクトップアプリ")
    ap.add_argument("--model", default=None, help="YOLO モデルのパス (.pt)")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    import webview
    from .api import Api

    model = _resolve_model(args)
    api = Api(model_path=model, engine_name="yolo", config_path=args.config)

    window = webview.create_window(
        "auto-mosaic",
        url=os.path.join(WEB_DIR, "index.html"),
        js_api=api,
        width=1280, height=860, min_size=(900, 600),
    )
    api.attach_window(window)
    try:
        webview.start()
    finally:
        api.jobs.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
