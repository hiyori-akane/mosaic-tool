"""配布物（フリーズ実行）でのモデル探索パス解決の検証。"""

import sys

import app.main as m


def test_bundle_dirs_includes_macos_app_parent(monkeypatch):
    # macOS .app: exe は Name.app/Contents/MacOS/ にある
    exe = "/Users/x/Desktop/auto-mosaic.app/Contents/MacOS/auto-mosaic"
    monkeypatch.setattr(sys, "executable", exe)
    dirs = m._bundle_dirs()
    assert "/Users/x/Desktop/auto-mosaic.app/Contents/MacOS" in dirs
    # 「.app と同じ場所」（バンドルの親）も候補に含まれる
    assert "/Users/x/Desktop" in dirs


def test_model_search_includes_app_parent_when_frozen(monkeypatch, tmp_path):
    appdir = tmp_path / "auto-mosaic.app" / "Contents" / "MacOS"
    appdir.mkdir(parents=True)
    exe = appdir / "auto-mosaic"
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    dirs = m._model_search_dirs()
    # 利用者が .app の隣に置いた models/ が探索対象に入る
    assert str(tmp_path / "models") in dirs


def test_user_models_dir_in_search(monkeypatch, tmp_path):
    # ~/auto-mosaic/models が最優先の探索候補に入る
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows 用
    expected = str(tmp_path / "auto-mosaic" / "models")
    dirs = m._model_search_dirs()
    assert dirs[0] == expected


def test_bundle_dirs_plain_executable(monkeypatch, tmp_path):
    # Windows onedir 等: exe と同じフォルダ＋その1つ上が候補（.app は無い）
    exe = tmp_path / "auto-mosaic" / "auto-mosaic.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(exe))
    dirs = m._bundle_dirs()
    assert str(exe.parent) in dirs        # .exe と同じフォルダ
    assert str(tmp_path) in dirs          # 展開フォルダの隣に置いた場合の保険
