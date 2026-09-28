"""App configuration: directories, preferences, shared constants."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

APP_NAME = "list2audio"

# Characters forbidden in file / folder names on Windows (plus POSIX extras).
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def is_windows() -> bool:
    return sys.platform.startswith("win")


def config_dir() -> Path:
    """Per-user config directory (created on demand)."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    """Where downloaded tooling (ffmpeg) lives."""
    if is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_NAME / "cache"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Caches" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_name(name: str, max_len: int = 150) -> str:
    """Make a string safe to use as a folder/file name on any OS."""
    cleaned = _INVALID_CHARS.sub("_", name).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    # no path traversal: never allow "." / ".." as (part of a) name
    cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"\.{2,}", "_", cleaned)
    if not cleaned:
        cleaned = "YT_Playlist"
    return cleaned[:max_len]


# ------------------------------ preferences -------------------------------

_PREFS_FILE = "preferences.json"

DEFAULT_PREFS: dict = {
    "dest": "",  # last download folder
    "profile": "universal",
    "format": "mp3",
    "bitrate": "192",
    "embed_metadata": True,
    "embed_thumbnail": True,
    "sponsorblock": False,
    "geometry": "",  # window size/position
}


def prefs_path() -> Path:
    return config_dir() / _PREFS_FILE


def load_prefs() -> dict:
    """Read preferences; corrupted/missing files fall back to defaults."""
    try:
        data = json.loads(prefs_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_PREFS)
    if not isinstance(data, dict):
        return dict(DEFAULT_PREFS)
    prefs = dict(DEFAULT_PREFS)
    prefs.update({k: v for k, v in data.items() if k in DEFAULT_PREFS})
    return prefs


def save_prefs(**updates) -> dict:
    """Merge updates into preferences and persist them."""
    prefs = load_prefs()
    prefs.update({k: v for k, v in updates.items() if k in DEFAULT_PREFS})
    try:
        prefs_path().write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # preferences are best-effort, never break the app
    return prefs


def default_dest() -> Path:
    """Sensible default download folder."""
    dest = load_prefs().get("dest") or ""
    if dest and Path(dest).exists():
        return Path(dest)
    music = Path.home() / "Music"
    if music.exists():
        return music
    return Path.home() / "Downloads"
