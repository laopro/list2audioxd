"""Download state: archive (already downloaded IDs), failure log, playlist folders."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .config import sanitize_name

ARCHIVE_NAME = "download_archive.txt"
FAILURES_NAME = "failures.jsonl"


class Archive:
    """yt-dlp download-archive with in-memory dedup.

    yt-dlp reads the file on every video; we keep a set in memory so large
    playlists don't re-read the file constantly, and rewrite it only when
    something new was downloaded (also de-duplicating entries written by a
    concurrent run).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._entries: set[str] = set()
        self._dirty = False
        if self.path.exists():
            try:
                text = self.path.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError):
                text = ""  # corrupt archive = start fresh (worst case: re-download)
            for line in text.splitlines():
                line = line.strip()
                # valid entries are "extractor video_id" (contain a space)
                if line and " " in line:
                    self._entries.add(line)

    def __contains__(self, entry: str) -> bool:
        with self._lock:
            return entry in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def add(self, entry: str) -> None:
        """Record an entry (``extractor video_id``), ignoring duplicates."""
        entry = entry.strip()
        if not entry:
            return
        with self._lock:
            if entry in self._entries:
                return
            self._entries.add(entry)
            self._dirty = True
            try:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(entry + "\n")
            except OSError:
                pass  # in-memory state still works for this session

    def save(self) -> None:
        """Rewrite the archive file (dedup + drop nothing)."""
        with self._lock:
            if not self._dirty:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(
                    "\n".join(sorted(self._entries)) + ("\n" if self._entries else ""),
                    encoding="utf-8",
                )
                tmp.replace(self.path)
            except OSError:
                pass
            self._dirty = False


class FailureLog:
    """Append-only JSONL log of videos that could not be downloaded."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def record(
        self,
        *,
        playlist: str,
        url: str,
        title: str,
        error: str,
        attempts: int = 1,
    ) -> None:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "playlist": playlist,
            "url": url,
            "title": title,
            "error": error[:500],
            "attempts": attempts,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows: list[dict] = []
        try:
            for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        except OSError:
            pass
        return rows


class PlaylistSession:
    """Everything that lives inside one playlist's output folder."""

    def __init__(self, dest_root: Path, playlist_title: str):
        self.title = playlist_title or "YT_Playlist"
        self.folder = Path(dest_root) / sanitize_name(self.title)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.archive = Archive(self.folder / ARCHIVE_NAME)
        self.failures = FailureLog(self.folder / FAILURES_NAME)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"PlaylistSession({self.folder!s})"
