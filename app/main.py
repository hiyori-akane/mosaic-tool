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


def _bundle_dirs():
    """配布物（実行ファイル / .app バンドル）が置かれた場所の候補。

    Windows の onedir は exe と同じフォルダ、macOS の .app は
    ``Name.app/Contents/MacOS/exe`` のため「.app と同じ場所」（バンドルの親）
    も候補に含める。
    """
    out = []
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    out.append(exe_dir)
    # macOS .app: 実行ファイルから上に辿って .app を見つけ、その親を足す
    p = exe_dir
    while p and p != os.path.dirname(p):
        if p.endswith(".app"):
            out.append(os.path.dirname(p))
            break
        p = os.path.dirname(p)
    # 実行ファイルフォルダの1つ上も候補（Windows で展開フォルダの隣に置いた場合も拾う）
    parent = os.path.dirname(exe_dir)
    if parent and parent != exe_dir:
        out.append(parent)
    return out


def _user_models_dir():
    """利用者が置く標準の models フォルダ（~/auto-mosaic/models）。

    .app を /Applications に置く macOS 等では、バンドル隣ではなくホーム配下が
    自然。Windows でも C:\\Users\\<name>\\auto-mosaic\\models として機能する。
    """
    return os.path.join(os.path.expanduser("~"), "auto-mosaic", "models")


def _model_search_dirs():
    """models/.pt を探索するディレクトリ群（優先順）。

    探索順:
      1. ~/auto-mosaic/models（利用者が置く標準の場所）
      2. リポジトリ直下 models/（開発時）
      3. 実行ファイル隣 / .app と同じ場所 / その親（配布物の隣に置いた場合）
      4. カレントの models/
    """
    dirs = [_user_models_dir(), os.path.join(ROOT, "models")]
    if getattr(sys, "frozen", False):
        for d in _bundle_dirs():
            dirs.append(os.path.join(d, "models"))
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
