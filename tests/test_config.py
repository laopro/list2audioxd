"""Config helpers tests."""

from pathlib import Path

from list2audio.config import save_prefs


def test_prefs_roundtrip(tmp_path, monkeypatch):
    from list2audio import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)

    save_prefs(dest=str(tmp_path / "music"), profile="light")
    loaded = config.load_prefs()
    assert loaded["profile"] == "light"
    assert loaded["dest"].endswith("music")


def test_corrupt_prefs_fall_back(tmp_path, monkeypatch):
    from list2audio import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "preferences.json").write_text("{{{", encoding="utf-8")
    loaded = config.load_prefs()
    assert loaded["profile"] == "universal"  # default


def test_unknown_keys_ignored(tmp_path, monkeypatch):
    from list2audio import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "preferences.json").write_text(
        '{"hacker": true, "profile": "full"}', encoding="utf-8"
    )
    loaded = config.load_prefs()
    assert "hacker" not in loaded
    assert loaded["profile"] == "full"


def test_default_dest_never_crashes(monkeypatch):
    from list2audio import config

    monkeypatch.setattr(config, "load_prefs", lambda: {"dest": ""})
    dest = config.default_dest()
    assert isinstance(dest, Path)


def test_prefs_path_is_file(tmp_path, monkeypatch):
    from list2audio import config

    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    assert config.prefs_path() == tmp_path / "preferences.json"
