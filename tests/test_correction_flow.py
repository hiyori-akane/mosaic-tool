"""補正データフロー（§8）の E2E 検証。GUI / 検出モデル不要で Api を直接叩く。"""

import os

import cv2
import numpy as np

from app import imaging
from app.api import Api


def _write_sample(path, h=240, w=320):
    img = (np.random.RandomState(1).rand(h, w, 3) * 255).astype(np.uint8)
    cv2.imwrite(path, img)
    return img


def _api(tmp_path):
    # engine は使わない（検出は手動補正のみ）
    return Api(model_path=None, engine_name="yolo",
               config_path=str(_repo_config()), synchronous_jobs=True)


def _repo_config():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "config.yaml")


def test_apply_correction_add_then_export(tmp_path):
    src = str(tmp_path / "in.png")
    img = _write_sample(src)
    h, w = img.shape[:2]

    api = _api(tmp_path)
    res = api.load_batch([src])
    item_id = res["items"][0]["id"]

    # 表示解像度を取得（ブリッジ往復の単位）
    view = api.get_view(item_id)
    dw, dh = view["disp_w"], view["disp_h"]

    # 表示解像度の「追加」マスク（中央の矩形）を dataURL 化
    add = np.zeros((dh, dw), np.uint8)
    add[dh // 4: 3 * dh // 4, dw // 4: 3 * dw // 4] = 255
    add_url = imaging.mask_to_data_url(add)

    out = api.apply_correction(item_id, add_url, None, {"block_px": 12})
    assert out["preview_dataurl"].startswith("data:image/")

    # add が原寸 final_mask に反映されている
    item = api.session.get(item_id)
    fm = item.final_mask()
    assert int(fm.max()) == 255
    assert fm[h // 2, w // 2] == 255      # 中央は対象
    assert fm[2, 2] == 0                  # 端は非対象

    # remove ブラシで中央を除外
    rem = np.zeros((dh, dw), np.uint8)
    rem[dh // 2 - 5: dh // 2 + 5, dw // 2 - 5: dw // 2 + 5] = 255
    api.apply_correction(item_id, None, imaging.mask_to_data_url(rem), None)
    assert api.session.get(item_id).final_mask()[h // 2, w // 2] == 0

    # 書き出し（同期 job）
    out_dir = str(tmp_path / "out")
    api.set_reviewed(item_id, True)
    job = api.export([item_id], out_dir, {"format": "png", "pattern": "{name}_mosaic"})
    assert "job_id" in job
    produced = os.path.join(out_dir, "in_mosaic.png")
    assert os.path.exists(produced)
    saved = cv2.imread(produced)
    assert saved.shape == img.shape


def test_add_brush_overrides_previous_remove(tmp_path):
    # 削除した領域を追加ブラシで塗り直すと再び対象に戻る（最後の操作を優先）
    src = str(tmp_path / "c.png")
    img = _write_sample(src)
    h, w = img.shape[:2]
    api = _api(tmp_path)
    item_id = api.load_batch([src])["items"][0]["id"]
    view = api.get_view(item_id)
    dw, dh = view["disp_w"], view["disp_h"]

    region = np.zeros((dh, dw), np.uint8)
    region[dh // 4: 3 * dh // 4, dw // 4: 3 * dw // 4] = 255
    url = imaging.mask_to_data_url(region)

    # まず削除 → 中央は対象外
    api.apply_correction(item_id, None, url, None)
    assert api.session.get(item_id).final_mask()[h // 2, w // 2] == 0
    # 同じ場所を追加 → 削除指定が解除され再び対象になる
    api.apply_correction(item_id, url, None, None)
    assert api.session.get(item_id).final_mask()[h // 2, w // 2] == 255


def test_check_unreviewed_warns(tmp_path):
    src = str(tmp_path / "a.png")
    _write_sample(src)
    api = _api(tmp_path)
    item_id = api.load_batch([src])["items"][0]["id"]
    chk = api.check_unreviewed([item_id])
    assert chk["count"] == 1
    api.set_reviewed(item_id, True)
    assert api.check_unreviewed([item_id])["count"] == 0


def test_invalid_pattern_falls_back(tmp_path):
    src = str(tmp_path / "p.png")
    _write_sample(src)
    api = _api(tmp_path)
    item_id = api.load_batch([src])["items"][0]["id"]
    api.set_reviewed(item_id, True)
    out_dir = str(tmp_path / "out")
    # 無効なフォーマット（存在しないキー）でもクラッシュせず既定名で出力
    api.export([item_id], out_dir, {"format": "png", "pattern": "{missing}/{name}"})
    files = os.listdir(out_dir)
    assert len(files) == 1
    assert "/" not in files[0] and "\\" not in files[0]


def test_load_batch_clears_previous_session(tmp_path):
    a = str(tmp_path / "a.png")
    _write_sample(a)
    b = str(tmp_path / "b.png")
    _write_sample(b)
    api = _api(tmp_path)
    api.load_batch([a])
    assert len(api.session.all()) == 1
    # 2回目の取り込みで古いセッションは破棄される
    api.load_batch([b])
    assert len(api.session.all()) == 1
    assert api.session.all()[0].name == "b.png"


def test_imread_imwrite_unicode_roundtrip(tmp_path):
    from app import imaging
    p = str(tmp_path / "画像_テスト.png")
    # 入力は cv2.imwrite を使わず作成（非ASCIIパスで失敗する経路を避ける）
    img = (np.random.RandomState(1).rand(240, 320, 3) * 255).astype(np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    with open(p, "wb") as f:
        f.write(buf.tobytes())
    loaded = imaging.imread_unicode(p)
    assert loaded is not None and loaded.shape == img.shape
    out = str(tmp_path / "出力_mosaic.png")
    assert imaging.imwrite_unicode(out, img) is True
    assert imaging.imread_unicode(out) is not None


def test_export_disambiguates_same_basename(tmp_path):
    # 異なるフォルダの同名 basename が上書きされず一意化される
    da = tmp_path / "a"
    da.mkdir()
    db = tmp_path / "b"
    db.mkdir()
    _write_sample(str(da / "foo.png"))
    _write_sample(str(db / "foo.png"))
    api = _api(tmp_path)
    ids = [it["id"] for it in api.load_batch([str(da / "foo.png"), str(db / "foo.png")])["items"]]
    for i in ids:
        api.set_reviewed(i, True)
    out_dir = str(tmp_path / "out")
    res = api.export(ids, out_dir, {"format": "png", "pattern": "{name}_mosaic"})
    assert "job_id" in res
    files = sorted(os.listdir(out_dir))
    assert files == ["foo_mosaic.png", "foo_mosaic_1.png"]


def test_load_batch_data_from_dataurl(tmp_path):
    # ドラッグ&ドロップ相当（ネイティブパス無し）の取り込み
    img = (np.random.RandomState(3).rand(80, 100, 3) * 255).astype(np.uint8)
    url = imaging.to_data_url(img, ".png")
    api = _api(tmp_path)
    res = api.load_batch_data([{"name": "dropped.png", "dataurl": url}])
    assert len(res["items"]) == 1
    assert res["items"][0]["name"] == "dropped.png"
    assert len(api.session.all()) == 1


def test_load_batch_data_falls_back_for_invalid_name(tmp_path):
    # name が None / 空 / 非文字列でも "image.png" に正規化される
    img = (np.random.RandomState(4).rand(80, 100, 3) * 255).astype(np.uint8)
    url = imaging.to_data_url(img, ".png")
    api = _api(tmp_path)

    for bad_name in (None, "", 123):
        res = api.load_batch_data([{"name": bad_name, "dataurl": url}])
        assert len(res["items"]) == 1
        assert res["items"][0]["name"] == "image.png"


def test_set_reviewed_returns_backend_status(tmp_path):
    src = str(tmp_path / "r.png")
    _write_sample(src)
    api = _api(tmp_path)
    item_id = api.load_batch([src])["items"][0]["id"]
    on = api.set_reviewed(item_id, True)
    assert on["status"] == "reviewed"
    # 未検出画像のチェックを外すと "none"（"detected" ではない）
    off = api.set_reviewed(item_id, False)
    assert off["status"] == "none"


def test_get_view_returns_display_resolution(tmp_path):
    # フル解像度を超える画像で、表示解像度に縮小されること（§3.3/§8）
    src = str(tmp_path / "big.png")
    _write_sample(src, h=4000, w=6000)
    api = _api(tmp_path)
    item_id = api.load_batch([src])["items"][0]["id"]
    view = api.get_view(item_id)
    assert view["disp_w"] <= imaging.DISPLAY_MAX_SIDE
    assert view["disp_h"] <= imaging.DISPLAY_MAX_SIDE
    assert view["scale"] < 1.0
