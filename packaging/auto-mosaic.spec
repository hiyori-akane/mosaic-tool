# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — auto-mosaic デスクトップ GUI を配布物にする。
#   mac:     dist/auto-mosaic.app
#   Windows: dist/auto-mosaic/auto-mosaic.exe
#
# 注意:
#  - 検出に torch / ultralytics が必要なため成果物は大きい（~1GB前後）。
#    検出を省いて手動補正のみの軽量ビルドにしたい場合は HEAVY_PKGS から
#    "torch"/"torchvision"/"ultralytics" を外す。
#  - モデル(.pt)はライセンス上同梱しない。利用者が実行ファイル隣の models/ に置く。
import os
import sys

from PyInstaller.utils.hooks import collect_all

# spec 内の相対パスは spec のあるディレクトリ基準で解決される。
# プロジェクトルートを SPECPATH から求め、エントリ/データを絶対パスで渡す
# （どの作業ディレクトリから実行しても壊れないようにする）。
ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821 (PyInstaller 注入)

# 同梱する静的アセット（GUI と既定設定）
datas = [
    (os.path.join(ROOT, "app", "web"), "app/web"),
    (os.path.join(ROOT, "config.yaml"), "."),
]
binaries = []
hiddenimports = []

# 動的 import が多いパッケージは丸ごと収集する
HEAVY_PKGS = ("ultralytics", "torch", "torchvision", "cv2", "webview", "yaml", "numpy")
for pkg in HEAVY_PKGS:
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, "desktop.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="auto-mosaic",
    console=False,            # GUI アプリ（コンソール窓を出さない）
    disable_windowed_traceback=False,
    icon=None,                # アイコンを用意したら packaging/ に置いて指定
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="auto-mosaic",
)

# macOS は .app バンドルにする
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="auto-mosaic.app",
        icon=None,
        bundle_identifier="dev.mosaic.auto-mosaic",
    )
