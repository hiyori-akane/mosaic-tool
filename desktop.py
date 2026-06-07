#!/usr/bin/env python3
"""PyInstaller 用のデスクトップ GUI 起動エントリ。

`python -m app.main` と同等。配布ビルド（mac .app / Windows .exe）は
このファイルを PyInstaller のエントリスクリプトに指定する。
"""

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
