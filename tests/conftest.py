import os
import sys

# リポジトリルートを import パスに追加（mosaic / app 用）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
