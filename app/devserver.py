"""ブラウザ検証ハーネス（検証専用・本番では使わない）。

``python -m app.devserver`` で web/ を配信し、実際の Api メソッドを
HTTP-RPC で呼べるようにする。これにより pywebview ウィンドウなしでも
取り込み→検出→補正→プレビュー→書き出しをブラウザで手動確認できる。

注意: 本番ブリッジは HTTP を使わない（仕様 §3.1）。これはあくまで開発・受け入れ
検証用のショートカット。ブリッジ往復のペイロードサイズをログ出力し、
ブラシ中にフル解像度 base64 が流れていないこと（仕様 §8/§12）を確認できる。
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# 公開 RPC メソッドの許可リスト（private/内部メソッドの露出を防ぐ）
_ALLOWED_METHODS = {
    "pick_files", "pick_folder", "load_batch", "load_batch_data",
    "detect", "detect_all", "get_view", "apply_correction", "set_params",
    "set_reviewed", "export", "check_unreviewed", "get_settings",
    "save_settings",
}


def build_handler(api):
    # ThreadingHTTPServer はリクエストごとに別スレッド。イベントはスレッドローカルに
    # 蓄積して取り違えを防ぐ。
    local = threading.local()
    api.jobs.set_emit(
        lambda fn, args: getattr(local, "events", []).append([fn, args]))

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=WEB_DIR, **k)

        def log_message(self, fmt, *args):  # 既定ログを抑制
            pass

        def do_POST(self):
            if self.path != "/rpc":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            req = json.loads(body or b"{}")
            method = req.get("method")
            args = req.get("args", [])

            # ブリッジ往復のペイロードサイズを計測（受け入れ基準 §12）
            print(f"[rpc] {method} req={length}B", flush=True)

            local.events = []
            try:
                if method not in _ALLOWED_METHODS:
                    raise AttributeError(f"method not allowed: {method}")
                fn = getattr(api, method)
                result = fn(*args)
                payload = {"result": result, "events": local.events}
            except Exception as e:  # noqa: BLE001
                payload = {"error": str(e), "events": local.events}

            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            print(f"[rpc] {method} resp={len(data)}B", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="auto-mosaic ブラウザ検証サーバ")
    ap.add_argument("--model", default=None)
    ap.add_argument("--engine", default="yolo", choices=["yolo"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    from .api import Api
    api = Api(model_path=args.model, engine_name=args.engine,
              config_path=args.config, synchronous_jobs=True)

    handler = build_handler(api)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}/index.html?dev=1"
    print(f"検証サーバ起動: {url}  (Ctrl-C で停止)", flush=True)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        t.join()
    except KeyboardInterrupt:
        print("\n停止します")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
