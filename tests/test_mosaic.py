import numpy as np

from mosaic.config import load_config
from mosaic.mosaic import apply_mosaic, blend, block_size, mosaic_image


def test_block_size_fixed():
    cfg = load_config()
    cfg.mosaic.mode = "fixed"
    cfg.mosaic.block_px = 10
    assert block_size(1000, 2000, cfg) == 10


def test_block_size_longside():
    cfg = load_config()
    cfg.mosaic.mode = "longside"
    cfg.mosaic.longside_div = 100
    cfg.mosaic.min_block_px = 4
    assert block_size(500, 2000, cfg) == 20      # 2000//100
    assert block_size(100, 100, cfg) == 4        # min_block_px


def test_apply_mosaic_keeps_shape():
    img = (np.random.rand(120, 160, 3) * 255).astype(np.uint8)
    out = apply_mosaic(img, 10)
    assert out.shape == img.shape


def test_apply_mosaic_blocks_constant():
    # 単一ブロック内はニアレスト拡大で概ね一定になる
    img = (np.random.rand(100, 100, 3) * 255).astype(np.uint8)
    out = apply_mosaic(img, 50)
    # 角の 50x50 ブロックは1色（NEAREST 拡大）に近い
    block = out[:50, :50]
    assert np.unique(block.reshape(-1, 3), axis=0).shape[0] <= 4


def test_blend_full_mask_is_mosaic():
    img = np.zeros((20, 20, 3), np.uint8)
    mosaic = np.full((20, 20, 3), 200, np.uint8)
    mask = np.full((20, 20), 255, np.uint8)
    out = blend(img, mosaic, mask)
    assert np.allclose(out, mosaic, atol=1)


def test_mosaic_image_empty_mask_returns_copy():
    cfg = load_config()
    img = (np.random.rand(40, 40, 3) * 255).astype(np.uint8)
    mask = np.zeros((40, 40), np.uint8)
    out = mosaic_image(img, mask, cfg)
    assert np.array_equal(out, img)
