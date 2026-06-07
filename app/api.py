"""JS↔Python ブリッジの公開メソッド（仕様 §6）。

重い処理（detect / export）は即 job_id を返し、進捗は JobManager 経由で push。
画素処理はすべてフル解像度で Python 側が担当し、ブリッジには表示解像度の
dataURL と小さな JSON しか流さない（仕様 §3.3 / §8）。
"""

from __future__ import annotations

import os
from typing import List, Optional

import cv2
import numpy as np

from mosaic.config import load_config
from mosaic.engines import get_engine
from mosaic.mask_ops import build_mask, blur_mask, expand
from mosaic.mosaic import mosaic_image

from . import imaging
from .jobs import JobManager
from .session import Session

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


class Api:
    def __init__(self, model_path: Optional[str] = None, engine_name: str = "yolo",
                 config_path: Optional[str] = None, window=None,
                 synchronous_jobs: bool = False):
        self.cfg = load_config(config_path)
        self.session = Session()
        self.jobs = JobManager(synchronous=synchronous_jobs)
        self._engine = None
        self._engine_name = engine_name
        self._model_path = model_path
        self._window = window
        self._detect_error = None

    # window は GUI 起動後に注入（devserver では別の emit を使う）
    def attach_window(self, window):
        self._window = window
        from .jobs import make_pywebview_emit
        self.jobs.set_emit(make_pywebview_emit(window))

    # -- エンジン（遅延ロード・1回だけ） -----------------------------------
    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            self._engine = get_engine(self._engine_name, self._model_path)
        except Exception as e:  # noqa: BLE001
            self._detect_error = str(e)
            raise
        return self._engine

    # =====================================================================
    # ファイル選択・取り込み
    # =====================================================================
    def pick_files(self) -> dict:
        if not self._window:
            return {"paths": []}
        import webview
        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True,
            file_types=("Images (*.png;*.jpg;*.jpeg;*.webp)",),
        )
        return {"paths": list(paths) if paths else []}

    def pick_folder(self) -> dict:
        if not self._window:
            return {"dir": ""}
        import webview
        res = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return {"dir": res[0] if res else ""}

    def load_batch(self, paths: List[str]) -> dict:
        # 新しいバッチで古いセッション（フル解像度画素）を破棄する。
        # フロントは setItems で表示を置き換えるため、Python 側も置き換えて
        # メモリ累積と「全件検出」での非表示画像への再処理を防ぐ。
        self.session.clear()
        items = []
        for p in paths:
            if os.path.isdir(p):
                try:
                    children = [os.path.join(p, f) for f in sorted(os.listdir(p))
                                if f.lower().endswith(IMG_EXTS)]
                except OSError:
                    # 権限なし／列挙中に削除された等。アプリ全体を落とさずスキップ。
                    children = []
            else:
                children = [p]
            for c in children:
                img = imaging.imread_unicode(c)  # 非ASCIIパス対応
                if img is None:
                    continue
                item = self.session.add(c, img)
                items.append({
                    "id": item.id, "name": item.name,
                    "w": item.w, "h": item.h,
                    "thumb_dataurl": imaging.make_thumb(img),
                    "status": item.status(),
                })
        return {"items": items}

    def load_batch_data(self, files: List[dict]) -> dict:
        """dataURL での取り込み（ドラッグ&ドロップ等、ネイティブパスが無い場合）。"""
        self.session.clear()
        items = []
        for f in files or []:
            if not isinstance(f, dict):
                continue
            img = imaging.data_url_to_image(f.get("dataurl"))
            if img is None:
                continue
            name = f.get("name")
            if not isinstance(name, str) or not name:
                name = "image.png"
            item = self.session.add(name, img)
            items.append({
                "id": item.id, "name": item.name,
                "w": item.w, "h": item.h,
                "thumb_dataurl": imaging.make_thumb(img),
                "status": item.status(),
            })
        return {"items": items}

    # =====================================================================
    # 検出（重い → job）
    # =====================================================================
    def detect(self, item_id: str) -> dict:
        return {"job_id": self.jobs.submit(lambda job: self._detect_ids([item_id], job))}

    def detect_all(self) -> dict:
        ids = self.session.ids()
        return {"job_id": self.jobs.submit(lambda job: self._detect_ids(ids, job))}

    def _detect_ids(self, ids, job) -> dict:
        engine = self._ensure_engine()
        total = len(ids)
        done = 0
        statuses = {}
        for item_id in ids:
            item = self.session.get(item_id)
            if item is not None:
                detections = engine.infer(item.original)
                item.model_mask = build_mask(detections, item.h, item.w, self.cfg)
                item.detected = True
                statuses[item_id] = item.status()
            done += 1
            job.progress(done, total, "detect")
        return {"phase": "detect", "count": done, "statuses": statuses}

    # =====================================================================
    # 表示（表示解像度の dataURL を返す＝1回きり）
    # =====================================================================
    def get_view(self, item_id: str) -> dict:
        item = self.session.get(item_id)
        if item is None:
            return {"error": "not found"}
        disp_img, scale = imaging.resize_to_display(item.original)
        dh, dw = disp_img.shape[:2]
        mask = item.final_mask()
        disp_mask = cv2.resize(mask, (dw, dh), interpolation=cv2.INTER_NEAREST)
        return {
            "image_dataurl": imaging.to_data_url(disp_img, ".jpg"),
            "mask_dataurl": imaging.mask_to_data_url(disp_mask),
            "disp_w": dw, "disp_h": dh, "scale": scale,
            "status": item.status(),
            "block_px": item.block_px or self.cfg.mosaic.block_px,
        }

    # =====================================================================
    # 補正の適用（追加/削除マスクは表示解像度の PNG dataURL）
    # =====================================================================
    def apply_correction(self, item_id: str, add_dataurl: Optional[str],
                         remove_dataurl: Optional[str], params: Optional[dict]) -> dict:
        item = self.session.get(item_id)
        if item is None:
            return {"error": "not found"}

        # 表示解像度マスク → 原寸 0/255。
        # 追加/削除は累積するが、重なった領域は「最後の操作」を優先する
        # （例: 削除した場所を追加ブラシで塗ると再び対象に戻せるようにする）。
        if add_dataurl:
            add = imaging.upscale_mask(imaging.data_url_to_image(add_dataurl, True),
                                       item.h, item.w)
            item.add_mask = add if item.add_mask is None else np.maximum(item.add_mask, add)
            # 追加した領域は削除指定から外す
            if item.remove_mask is not None:
                item.remove_mask[add > 0] = 0
        if remove_dataurl:
            rem = imaging.upscale_mask(imaging.data_url_to_image(remove_dataurl, True),
                                       item.h, item.w)
            item.remove_mask = rem if item.remove_mask is None else \
                np.maximum(item.remove_mask, rem)
            # 削除した領域は追加指定から外す
            if item.add_mask is not None:
                item.add_mask[rem > 0] = 0

        if params and params.get("block_px"):
            item.block_px = int(params["block_px"])

        preview = self._render_full(item)
        disp_preview, _ = imaging.resize_to_display(preview)
        return {"preview_dataurl": imaging.to_data_url(disp_preview, ".jpg")}

    def _render_full(self, item) -> np.ndarray:
        """フル解像度で final_mask → grow/blur → モザイク合成。"""
        mask = item.final_mask()
        mask = expand(mask, self.cfg.mask.overall_grow_px)
        mask = blur_mask(mask, self.cfg.mask.blur_sigma)
        return mosaic_image(item.original, mask, self.cfg, block=item.block_px)

    # =====================================================================
    # パラメータ・状態
    # =====================================================================
    def set_params(self, scope: str, params: dict) -> dict:
        if scope == "global":
            if params.get("block_px"):
                self.cfg.mosaic.block_px = int(params["block_px"])
        else:
            item = self.session.get(scope)
            if item and params.get("block_px"):
                item.block_px = int(params["block_px"])
        return {"ok": True}

    def set_reviewed(self, item_id: str, value: bool) -> dict:
        item = self.session.get(item_id)
        if item is None:
            return {"ok": False}
        item.reviewed = bool(value)
        # フロントが正しいバッジに更新できるよう、確定後の status を返す
        return {"ok": True, "status": item.status()}

    # =====================================================================
    # 書き出し（重い → job）
    # =====================================================================
    def export(self, ids: List[str], out_dir: str, options: Optional[dict]) -> dict:
        options = options or {}
        return {"job_id": self.jobs.submit(
            lambda job: self._export(ids, out_dir, options, job))}

    def _export(self, ids, out_dir, options, job) -> dict:
        os.makedirs(out_dir, exist_ok=True)
        fmt = options.get("format", "png").lower()
        pattern = options.get("pattern", "{name}_mosaic")
        ext = ".jpg" if fmt in ("jpg", "jpeg") else ".png"

        total = len(ids)
        done = 0
        written = []
        used_names = set()
        for item_id in ids:
            item = self.session.get(item_id)
            if item is not None:
                out = self._render_full(item)
                stem = os.path.splitext(item.name)[0]
                base = self._format_name(pattern, stem)
                # 同名 basename 同士で上書きしないよう一意化する
                fname = f"{base}{ext}"
                suffix = 1
                while fname in used_names or os.path.exists(os.path.join(out_dir, fname)):
                    fname = f"{base}_{suffix}{ext}"
                    suffix += 1
                used_names.add(fname)
                out_path = os.path.join(out_dir, fname)
                if imaging.imwrite_unicode(out_path, out):  # 非ASCIIパス対応
                    written.append(out_path)
            done += 1
            job.progress(done, total, "export")
        return {"phase": "export", "count": len(written),
                "out_dir": out_dir, "files": written}

    @staticmethod
    def _format_name(pattern: str, stem: str) -> str:
        """命名規則を安全に適用。無効なフォーマット文字列は既定にフォールバック。"""
        if not isinstance(pattern, str):
            pattern = "{name}_mosaic"
        try:
            name = pattern.format(name=stem)
        except (KeyError, IndexError, ValueError):
            name = f"{stem}_mosaic"
        # パス区切りや空名を防ぐ
        name = name.replace("/", "_").replace("\\", "_").strip()
        return name or f"{stem}_mosaic"

    def check_unreviewed(self, ids: List[str]) -> dict:
        """書き出し前の未確認警告（仕様 §5.4 / §12）。"""
        unreviewed = [i for i in ids
                      if (it := self.session.get(i)) and not it.reviewed]
        return {"unreviewed": unreviewed, "count": len(unreviewed)}

    # =====================================================================
    # 設定
    # =====================================================================
    def get_settings(self) -> dict:
        return {
            "block_px": self.cfg.mosaic.block_px,
            "mode": self.cfg.mosaic.mode,
            "blur_sigma": self.cfg.mask.blur_sigma,
            "engine": self._engine_name,
            "model_loaded": self._engine is not None,
            "detect_error": self._detect_error,
        }

    def save_settings(self, settings: dict) -> dict:
        if not settings:
            return {"ok": False}
        if settings.get("block_px"):
            self.cfg.mosaic.block_px = int(settings["block_px"])
        if settings.get("mode"):
            self.cfg.mosaic.mode = str(settings["mode"])
        return {"ok": True}
