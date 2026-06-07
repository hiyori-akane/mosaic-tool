# Auto-Mosaic (YOLO GUI / CLI)

ComfyUI の ワークフローを移植した自動モザイク付与ツールです。
ultralytics YOLO segmentation で対象を検出し、マスク後処理 → モザイク合成を行います。

- **デスクトップ GUI**（pywebview）: 取り込み → 検出 → とりこぼし補正 → 書き出し
- **CLI**: フォルダー/単一画像の一括処理

> 検出ロジック・パラメータは ComfyUI 由来。マスク後処理・モザイクのコア
> （`mosaic/`）は GUI と CLI で共有しています。

## ワークフローの再現仕様

- **検出モデル**: `ntd11_anime_nsfw_segm_v5.pt`（ultralytics YOLO segmentation）
- **検出系統とパラメータ**:
  1. **性器系**（`pussy`, `anus`, `penis`, `testicles`, `x-ray`, `cross-section`）: `conf` ≥ 0.50, `dilate` = 2px
  2. **乳首**（`nipples`）: `conf` ≥ 0.01（高感度検出）, `dilate` = 50px + `grow` = 10px
- **マスク処理**: 2系統を `OR` 合成 → 全体 `grow` = 2px → ガウシアンぼかし（`sigma` = 10）
- **モザイク処理**: `Lanczos4` 縮小 → `Nearest` 拡大。実効ブロックサイズは既定 **10px**

これらの値は `config.yaml` で調整できます（GUI / CLI 共通）。

## 構成

```
mosaic-tool/
├─ mosaic/                  # コア（検出エンジン・マスク後処理・モザイク・CLI）
│  ├─ config.py             # config.yaml ロード + 既定値
│  ├─ mask_ops.py           # build_mask / expand / blur
│  ├─ mosaic.py             # apply_mosaic / blend / mosaic_image
│  ├─ cli.py                # バッチ CLI
│  └─ engines/              # base.py（Detection / DetectorEngine）+ engine_yolo.py
├─ app/                     # デスクトップ GUI（pywebview + HTML/JS）
│  ├─ main.py               # 起動エントリ
│  ├─ api.py                # JS↔Python ブリッジ
│  ├─ devserver.py          # ブラウザ検証用サーバ
│  └─ web/                  # index.html / css / js
├─ config.yaml              # 共通パラメータ
├─ mosaic.py                # 旧 CLI 互換シム（→ mosaic.cli）
└─ tests/                   # pytest
```

## セットアップ

```bash
chmod +x setup.sh
./setup.sh
```

スクリプトは仮想環境 `.venv` の作成、依存のインストール、`models/` の作成、
（存在すれば）ComfyUI からのモデルコピーを行います。

> [!NOTE]
> モデルが見つからない場合は手動で `models/ntd11_anime_nsfw_segm_v5.pt` に配置してください。
>
> 1. **モデルページ**: [Anime NSFW Detection / ADetailer All-in-One (Civitai)](https://civitai.com/models/1313556/anime-nsfw-detection-adetailer-all-in-one)
> 2. **設定**: NSFW モデルのため、Civitai にログインし成人向けコンテンツ表示を ON にする必要があります。
> 3. **ダウンロード**: バージョン **`v5.0-variant1`** を選択して取得してください。

GUI を使う場合は依存に `pywebview` が含まれます（`requirements.txt`）。手動なら:

```bash
pip install -r requirements.txt
```

## 使い方（GUI）

```bash
source .venv/bin/activate
python -m app.main            # models/ 配下の .pt を自動検出して使用
# モデルを明示する場合:
python -m app.main --model models/ntd11_anime_nsfw_segm_v5.pt
```

取り込み（ドラッグ&ドロップ / ファイル選択）→ 検出 → ブラシで補正（追加/削除）→
確認 → 書き出し、の流れで操作します。元画像は上書きしません。

### ブラウザで動作確認（任意）

GUI を起動せずブラウザで UI を確認したい場合:

```bash
python -m app.devserver       # http://127.0.0.1:8765
```

## 使い方（CLI）

```bash
source .venv/bin/activate

# フォルダを一括処理
python -m mosaic.cli /path/to/input_folder -o /path/to/output_folder

# 単一画像
python -m mosaic.cli /path/to/image.png -o /path/to/output_folder

# 旧来の呼び方（互換シム）も可
python mosaic.py /path/to/input_folder -o /path/to/output_folder
```

### 主な引数
- `input`: 入力画像ファイル または フォルダ
- `-o`, `--output`: 出力先フォルダ（既定 `./out`）
- `--model`: YOLO モデル(.pt)のパス（既定 `models/ntd11_anime_nsfw_segm_v5.pt`）
- `--device`: 推論デバイス（`cpu` / `mps` / `cuda`。既定は ultralytics 自動）
- `--config`: `config.yaml` のパス

## サンプルデータでの動作テスト

```bash
mkdir -p Pictures/in Pictures/out
curl -L -o Pictures/in/sample1.jpg https://huggingface.co/datasets/Bl4ckSpaces/NSFW-ANIME-2D-DATASET-RAW/resolve/main/generated_1771198018_7ad010a3.jpg
curl -L -o Pictures/in/sample2.jpg https://huggingface.co/datasets/Bl4ckSpaces/NSFW-ANIME-2D-DATASET-RAW/resolve/main/generated_1771198023_0ccf23dd.jpg

source .venv/bin/activate
python -m mosaic.cli Pictures/in -o Pictures/out
```

`Pictures/out/` に処理結果が出力されます。

## パラメータ調整（`config.yaml`）

- `mosaic.block_px`: モザイクのブロックサイズ（既定 10px）
- `mosaic.mode`: `fixed`（固定） / `longside`（長辺基準: `max(min_block_px, longside // longside_div)`）
- `groups.*.conf`: 各系統の検出しきい値（誤検出が多い場合は上げる）
- `mask.blur_sigma`: 縁のぼかし強度

## テスト

```bash
python -m pytest -q
```

## 配布ビルド（mac .app / Windows .exe）

GitHub Actions（`.github/workflows/release.yml`）で、`v*` タグ（例 `v0.1.0`）を push すると
mac と Windows のランナー上で PyInstaller ビルドを行い、同名リリースに zip を添付します。

```bash
git tag v0.1.0
git push origin v0.1.0     # → リリースに auto-mosaic-macos.zip / auto-mosaic-windows.zip が付く
```

ローカルで試す場合:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm packaging/auto-mosaic.spec
# 成果物: dist/auto-mosaic.app（mac） / dist/auto-mosaic/auto-mosaic.exe（Windows）
```

注意点:
- **モデルは同梱しません**（ライセンスのため）。利用者は実行ファイル隣の `models/` に
  `.pt` を置いてください（アプリは隣・カレントの `models/` も探索します）。
- 検出に torch/ultralytics を含むため成果物は大きめ（~1GB前後）。検出不要なら
  `packaging/auto-mosaic.spec` の `HEAVY_PKGS` から torch 等を外すと軽量化できます。
- **コード署名なし**だと、macOS は Gatekeeper、Windows は SmartScreen の警告が出ます。
  正式配布には Apple Developer 署名/notarization・Windows コード署名証明書が別途必要です。
- Windows は **WebView2 ランタイム**が必要（Win11 は標準同梱、Win10 は要インストール）。

## 配布版の使い方（利用者向け）

リリースから zip をダウンロードして展開してください。当面は**コード署名なし**で配布するため、
初回起動時に OS の警告が出ます。以下の手順で起動できます。

### 1. モデル(.pt)を置く

検出モデルは同梱していません（ライセンスのため）。`ntd11_anime_nsfw_segm_v5.pt` を入手し、
**実行ファイルの隣に `models/` フォルダを作って**入れてください（モデルが無い場合は手動補正のみ動作します）。

```
auto-mosaic.app（または auto-mosaic.exe）と同じ場所に:
  models/ntd11_anime_nsfw_segm_v5.pt
```

### 2. 起動（未署名のため警告が出ます）

**macOS**（Gatekeeper の警告）
- `auto-mosaic.app` を**右クリック →「開く」→「開く」**（初回のみ。2回目以降は通常起動）。
- 「壊れている／開けません」と出る場合は、ダウンロード時に付く隔離属性を外します:
  ```bash
  xattr -dr com.apple.quarantine /path/to/auto-mosaic.app
  ```

**Windows**（SmartScreen の警告）
- 「WindowsによってPCが保護されました」が出たら、**「詳細情報」→「実行」**。
- 起動しない場合は **WebView2 ランタイム**が必要です（Windows 11 は標準同梱。Windows 10 は
  Microsoft 配布の「Evergreen ランタイム」をインストール）。

> 正式に署名済みで配布する場合は、Apple Developer の署名/notarization、Windows のコード署名
> 証明書が別途必要です（将来対応予定）。

## ライセンス

本リポジトリの**ソースコード**は **GNU AGPL-3.0**（`LICENSE`）で配布します。
検出に使う **ultralytics YOLO 自体が AGPL-3.0** のため、それを利用する本ツールも
AGPL-3.0 としています（ネットワーク経由で提供する場合も含め、利用者へ対応するソース
コードを提供する義務があります）。
