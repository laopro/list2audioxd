"""Dependency checks / bootstrap (yt-dlp + ffmpeg).

Design goal: a non-technical Windows user should never see a terminal.
On Windows we auto-download a static ffmpeg build into our cache folder.
"""

from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from .config import cache_dir, is_windows

# Static Windows builds of ffmpeg (essentials: mp3/m4a/opus/flac/wav encoders).
FFMPEG_ZIP_URLS = [
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z",  # fallback marker
]

ProgressCb = Callable[[str], None]


class DependencyError(RuntimeError):
    """Raised when a required dependency is missing and cannot be auto-fixed."""


def yt_dlp_version() -> str:
    try:
        from importlib.metadata import version

        return version("yt-dlp")
    except Exception:
        try:
            import yt_dlp

            return getattr(yt_dlp, "version", "?")
        except Exception:
            return "missing"


def has_yt_dlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def _find_ffmpeg_in(path: Path) -> Path | None:
    exe = "ffmpeg.exe" if is_windows() else "ffmpeg"
    if path.is_file() and path.name == exe:
        return path
    if path.is_dir():
        # direct child or any depth-2 child (zip layouts vary: bin/, ffmpeg/bin/)
        for candidate in (path / exe, path / "bin" / exe):
            if candidate.is_file():
                return candidate
        for candidate in path.rglob(exe):
            return candidate
    return None


def find_ffmpeg() -> Path | None:
    """Locate ffmpeg: env var > app cache > system PATH."""
    env = shutil.which("ffmpeg")
    if env:
        return Path(env)
    cached = cache_dir() / "ffmpeg"
    if cached.exists():
        found = _find_ffmpeg_in(cached)
        if found:
            return found
    return None


def _download(url: str, dest: Path, label: ProgressCb | None = None) -> None:
    if label:
        label(f"Downloading {url.rsplit('/', 1)[-1]} ...")

    def _hook(blocks: int, block_size: int, total: int) -> None:
        if label and total > 0:
            done = blocks * block_size
            pct = min(100, int(done * 100 / total))
            label(f"Downloading ffmpeg... {pct}%")

    urllib.request.urlretrieve(url, dest, reporthook=_hook)


def ensure_ffmpeg(label: ProgressCb | None = None, interactive: bool = True) -> Path:
    """Return a usable ffmpeg path, downloading it on Windows if needed.

    Raises DependencyError on non-Windows when ffmpeg is missing.
    """
    found = find_ffmpeg()
    if found:
        return found

    if not is_windows():
        raise DependencyError(
            "ffmpeg not found. Install it first:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  Fedora:       sudo dnf install ffmpeg\n"
            "  Arch:         sudo pacman -S ffmpeg\n"
            "  macOS:        brew install ffmpeg"
        )

    target_root = cache_dir() / "ffmpeg"
    zip_path = cache_dir() / "ffmpeg.zip"

    for url in FFMPEG_ZIP_URLS:
        if url.endswith(".7z"):
            continue  # we only auto-extract zip
        try:
            _download(url, zip_path, label)
            if label:
                label("Extracting ffmpeg...")
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(target_root)
            zip_path.unlink(missing_ok=True)
        except Exception as exc:  # network/disk problems: try next mirror
            if label:
                label(f"ffmpeg download failed ({exc}), trying next mirror...")
            continue
        found = _find_ffmpeg_in(target_root)
        if found:
            # make it executable just in case
            try:
                found.chmod(0o755)
            except OSError:
                pass
            if label:
                label("ffmpeg ready.")
            return found

    raise DependencyError(
        "Could not download ffmpeg automatically.\n"
        "Download it manually from https://www.gyan.dev/ffmpeg/builds/ "
        "and add its bin folder to PATH, then restart the app."
    )


def ensure_all(label: ProgressCb | None = None) -> dict:
    """Verify everything the engine needs. Returns {yt_dlp, ffmpeg} info."""
    if not has_yt_dlp():
        raise DependencyError(
            "yt-dlp is not installed.\n"
            "Run:  pip install -U yt-dlp   (or reinstall list2audio)"
        )
    ffmpeg = ensure_ffmpeg(label=label)
    return {"yt_dlp": yt_dlp_version(), "ffmpeg": str(ffmpeg)}


def self_update_yt_dlp(label: ProgressCb | None = None) -> bool:
    """Best-effort yt-dlp self-update (YouTube changes break old versions)."""
    if label:
        label("Checking yt-dlp is up to date...")
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            ydl.__class__.update()  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


if __name__ == "__main__":  # pragma: no cover
    print("python:", sys.version)
    print("yt-dlp:", yt_dlp_version())
    print("ffmpeg:", find_ffmpeg())
