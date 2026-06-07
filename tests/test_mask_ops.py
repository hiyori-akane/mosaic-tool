import numpy as np

from mosaic.config import load_config
from mosaic.engines.base import Detection
from mosaic.mask_ops import build_mask, expand


def _cfg():
    return load_config()


def test_expand_grows_region():
    m = np.zeros((50, 50), np.uint8)
    m[25, 25] = 255
    grown = expand(m, 5)
    assert int(grown.sum()) > int(m.sum())
    # 中心は前景のまま
    assert grown[25, 25] == 255


def test_expand_zero_is_noop():
    m = np.zeros((10, 10), np.uint8)
    m[5, 5] = 255
    assert np.array_equal(expand(m, 0), m)


def test_build_mask_genital_above_conf():
    cfg = _cfg()
    h = w = 100
    seg = np.zeros((h, w), np.float32)
    seg[40:60, 40:60] = 1.0
    det = Detection(mask=seg, cls="pussy", score=0.9, bbox=(40, 40, 60, 60))
    mask = build_mask([det], h, w, cfg)
    assert int(mask.max()) > 0
    assert mask[50, 50] > 0


def test_build_mask_genital_below_conf_dropped():
    cfg = _cfg()
    h = w = 100
    seg = np.zeros((h, w), np.float32)
    seg[40:60, 40:60] = 1.0
    # genital conf 0.50 未満は無視される
    det = Detection(mask=seg, cls="pussy", score=0.3, bbox=(40, 40, 60, 60))
    mask = build_mask([det], h, w, cfg)
    assert int(mask.max()) == 0


def test_build_mask_nipple_low_conf_kept():
    cfg = _cfg()
    h = w = 200
    seg = np.zeros((h, w), np.float32)
    seg[90:110, 90:110] = 1.0
    # nipple は conf 0.01 で拾う（高Recall）
    det = Detection(mask=seg, cls="nipple", score=0.02, bbox=(90, 90, 110, 110))
    mask = build_mask([det], h, w, cfg)
    assert int(mask.max()) > 0


def test_build_mask_drop_small_detection():
    cfg = _cfg()
    h = w = 100
    seg = np.zeros((h, w), np.float32)
    seg[50:55, 50:55] = 1.0
    # bbox 辺長 5 < drop_size_px(10) → 無視
    det = Detection(mask=seg, cls="pussy", score=0.9, bbox=(50, 50, 55, 55))
    mask = build_mask([det], h, w, cfg)
    assert int(mask.max()) == 0


def test_load_config_rejects_non_mapping_yaml(tmp_path):
    from mosaic.config import load_config
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        load_config(str(bad))


def test_load_config_missing_explicit_path_raises(tmp_path):
    from mosaic.config import load_config
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path / "nope.yaml"))
