"""バックグラウンド実行と進捗 push。

重い処理（検出・書き出し）を ThreadPoolExecutor で実行し、進捗・完了・エラーを
フロントへ push する。push 先は注入された ``emit`` コールバック（本番は
window.evaluate_js、検証時はスタブ）。
"""

from __future__ import annotations

import json
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional


class JobManager:
    def __init__(self, emit: Optional[Callable[[str, list], None]] = None,
                 max_workers: int = 2, synchronous: bool = False):
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        # emit(fn_name, args_list) -> フロントの window[fn_name](*args) を呼ぶ
        self._emit = emit or (lambda fn, args: None)
        # 検証用: True なら submit を同期実行（devserver でイベントを捕捉するため）
        self._synchronous = synchronous

    def set_emit(self, emit: Callable[[str, list], None]) -> None:
        self._emit = emit

    # -- イベント push ------------------------------------------------------
    def on_progress(self, job_id: str, done: int, total: int, phase: str) -> None:
        self._emit("onProgress", [job_id, done, total, phase])

    def on_done(self, job_id: str, result) -> None:
        self._emit("onJobDone", [job_id, result])

    def on_error(self, job_id: Optional[str], message: str) -> None:
        self._emit("onError", [job_id, message])

    # -- 実行 ---------------------------------------------------------------
    def submit(self, fn: Callable[["JobHandle"], object]) -> str:
        """fn(job) をバックグラウンド実行し job_id を即返す。

        fn は JobHandle を受け取り、進捗報告と戻り値（=完了結果）に責任を持つ。
        """
        job_id = uuid.uuid4().hex[:12]
        handle = JobHandle(self, job_id)

        def _run():
            try:
                result = fn(handle)
                self.on_done(job_id, result)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.on_error(job_id, str(e))

        if self._synchronous:
            _run()
        else:
            self._pool.submit(_run)
        return job_id

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)


class JobHandle:
    def __init__(self, manager: JobManager, job_id: str):
        self._m = manager
        self.job_id = job_id

    def progress(self, done: int, total: int, phase: str = "") -> None:
        self._m.on_progress(self.job_id, done, total, phase)


def make_pywebview_emit(window):
    """pywebview の window から evaluate_js ベースの emit を作る。"""
    def emit(fn_name: str, args: list) -> None:
        payload = ", ".join(json.dumps(a, ensure_ascii=False) for a in args)
        window.evaluate_js(f"window.{fn_name} && window.{fn_name}({payload})")
    return emit
