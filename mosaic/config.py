"""config.yaml の読み込みと既定値。

GUI / CLI が共有する設定。pyyaml が無い環境でも内蔵の既定値で動くように
フォールバックする（堅牢性のため）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# config.yaml が無い／読めない場合に使う既定値（仕様 §5/§9）
_DEFAULTS = {
    "groups": {
        "genital": {
            "classes": [
                "pussy", "penis", "testicles", "anus", "sex",
                "cross_section", "xray", "x-ray", "cross-section",
            ],
            "conf": 0.50,
            "dilate_px": 2,
        },
        "nipple": {
            "classes": ["nipple", "nipples"],
            "conf": 0.01,
            "dilate_px": 50,
            "grow_px": 10,
        },
    },
    "mask": {"overall_grow_px": 2, "blur_sigma": 10, "drop_size_px": 10},
    "mosaic": {
        "mode": "fixed",
        "block_px": 10,
        "longside_div": 100,
        "min_block_px": 4,
    },
}


@dataclass
class GroupConfig:
    classes: frozenset
    conf: float
    dilate_px: int
    grow_px: int = 0


@dataclass
class MaskConfig:
    overall_grow_px: int = 2
    blur_sigma: float = 10.0
    drop_size_px: int = 10


@dataclass
class MosaicConfig:
    mode: str = "fixed"
    block_px: int = 10
    longside_div: int = 100
    min_block_px: int = 4


@dataclass
class Config:
    genital: GroupConfig
    nipple: GroupConfig
    mask: MaskConfig
    mosaic: MosaicConfig

    def group_of(self, class_name: str) -> Optional[str]:
        """クラス名（小文字）が属するグループ名を返す。未知は None。"""
        name = str(class_name).lower()
        if name in self.genital.classes:
            return "genital"
        if name in self.nipple.classes:
            return "nipple"
        return None

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        d = _merge(_DEFAULTS, data or {})
        g = d["groups"]["genital"]
        n = d["groups"]["nipple"]
        return cls(
            genital=GroupConfig(
                classes=frozenset(s.lower() for s in g["classes"]),
                conf=float(g["conf"]),
                dilate_px=int(g["dilate_px"]),
                grow_px=int(g.get("grow_px", 0)),
            ),
            nipple=GroupConfig(
                classes=frozenset(s.lower() for s in n["classes"]),
                conf=float(n["conf"]),
                dilate_px=int(n["dilate_px"]),
                grow_px=int(n.get("grow_px", 0)),
            ),
            mask=MaskConfig(
                overall_grow_px=int(d["mask"]["overall_grow_px"]),
                blur_sigma=float(d["mask"]["blur_sigma"]),
                drop_size_px=int(d["mask"]["drop_size_px"]),
            ),
            mosaic=MosaicConfig(
                mode=str(d["mosaic"]["mode"]),
                block_px=int(d["mosaic"]["block_px"]),
                longside_div=int(d["mosaic"]["longside_div"]),
                min_block_px=int(d["mosaic"]["min_block_px"]),
            ),
        )


def _merge(base: dict, override: dict) -> dict:
    """base を override で再帰的に上書きした新しい dict を返す。"""
    out = {}
    for k, v in base.items():
        if k in override and isinstance(v, dict) and isinstance(override[k], dict):
            out[k] = _merge(v, override[k])
        elif k in override:
            out[k] = override[k]
        else:
            out[k] = v
    # base に無いキーも取り込む
    for k, v in override.items():
        if k not in out:
            out[k] = v
    return out


def _default_config_path() -> str:
    # リポジトリ直下の config.yaml（mosaic/ の親）
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config.yaml")


def load_config(path: Optional[str] = None) -> Config:
    """config.yaml を読み込んで Config を返す。

    明示的に path を渡した場合、ファイルが無い／壊れている時は例外を投げる
    （設定が黙って無視されて誤ったマスク強度になるのを防ぐ）。path 未指定時は
    既定パスを試し、読めなければ内蔵の既定値にフォールバックする。
    """
    explicit = path is not None
    path = path or _default_config_path()
    data = {}
    if path and os.path.exists(path):
        try:
            import yaml  # pyyaml は配布コア依存に含める
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            if loaded is None:
                data = {}
            elif isinstance(loaded, dict):
                data = loaded
            else:
                # トップレベルがマッピングでない（list/str 等）は不正
                raise ValueError(f"config の最上位はマッピングである必要があります: {path}")
        except Exception:
            if explicit:
                raise
            data = {}
    elif explicit:
        raise FileNotFoundError(path)
    return Config.from_dict(data)
