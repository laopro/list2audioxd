"""Download engine: yt-dlp as a library (not a subprocess).

Responsibilities:
  * fetch playlist metadata before downloading (title, count, entries)
  * run downloads one entry at a time -> precise progress + per-song errors
  * retries for transient errors, clean report for permanent ones
  * cancellation, incremental downloads via download-archive
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse

from .profiles import Profile
from .state import Archive, PlaylistSession

# ------------------------------- public types ------------------------------


@dataclass
class Progress:
    """UI-facing progress event."""

    index: int = 0  # 1-based current entry
    total: int = 0
    title: str = ""
    phase: str = "idle"  # idle | fetching | downloading | postprocessing | done
    percent: float = 0.0  # percent of the CURRENT entry
    skipped: int = 0  # entries skipped via archive
    message: str = ""

    @property
    def overall_percent(self) -> float:
        """Rough playlist-level progress (skips count as done)."""
        if self.total <= 0:
            return 0.0
        done = (self.index - 1) + (self.percent / 100.0)
        return max(0.0, min(100.0, done * 100.0 / self.total))


@dataclass
class Report:
    """Final result of a run - always honest about failures."""

    playlist_title: str = ""
    out_dir: Path | None = None
    ok: list[str] = field(default_factory=list)  # titles downloaded
    skipped: list[str] = field(default_factory=list)  # already had
    failed: list[tuple[str, str]] = field(default_factory=list)  # (title, error)
    cancelled: bool = False

    @property
    def total(self) -> int:
        return len(self.ok) + len(self.skipped) + len(self.failed)

    @property
    def success(self) -> bool:
        return not self.failed and not self.cancelled


class Hooks(Protocol):
    """Callbacks the CLI/GUI implement (all optional)."""

    def on_progress(self, progress: Progress) -> None: ...

    def on_log(self, message: str) -> None: ...


class _NullHooks:
    def on_progress(self, progress: Progress) -> None:
        pass

    def on_log(self, message: str) -> None:
        pass


class _YDLLogger:
    """yt-dlp logger adapter: quiet on debug/info, deduped warnings/errors.

    Without this, yt-dlp spams the console/GUI with the same warning dozens of
    times (e.g. one per entry of a playlist).
    """

    def __init__(self, hooks: Hooks) -> None:
        self._hooks = hooks
        self._seen: set[str] = set()

    def debug(self, message: str) -> None:
        pass  # yt-dlp progress/verbose chatter: we have our own progress UI

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        self._emit(message)

    def error(self, message: str) -> None:
        self._emit(message)

    def _emit(self, message: str) -> None:
        if message in self._seen:
            return
        self._seen.add(message)
        self._hooks.on_log(message)


# ------------------------------- cancellation ------------------------------


class CancelToken:
    """Thread-safe cancellation flag + yt-dlp interrupter."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    # yt-dlp side -----------------------------------------------------------
    def interrupt(self) -> None:  # called from yt-dlp hooks
        if self._cancelled:
            raise KeyboardInterrupt


# ------------------------------ error classes ------------------------------

_TRANSIENT_MARKERS = (
    "urlopen error",
    "connection reset",
    "connection refused",
    "timed out",
    "timeout",
    "temporary failure in name resolution",
    "network is unreachable",
    "http error 429",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
)


def is_transient_error(message: str) -> bool:
    """True for errors worth retrying (network hiccups)."""
    low = message.lower()
    return any(marker in low for marker in _TRANSIENT_MARKERS)


# --------------------------------- engine ----------------------------------


class Engine:
    """Downloads playlists according to a Profile."""

    def __init__(
        self,
        profile: Profile,
        *,
        ffmpeg_path: str | None = None,
        cookies_from_browser: bool = False,
        proxy: str | None = None,
        retries: int = 2,
        hooks: Hooks | None = None,
        cancel: CancelToken | None = None,
        js_runtimes: dict | None = None,
    ) -> None:
        profile.validate()
        self.profile = profile
        self.ffmpeg_location = str(ffmpeg_path) if ffmpeg_path else None
        self.cookies_from_browser = cookies_from_browser
        self.proxy = proxy
        self.retries = max(0, retries)
        self.hooks: Hooks = hooks or _NullHooks()
        self.cancel = cancel or CancelToken()
        # yt-dlp needs a JS runtime for YouTube (signature solving); detection
        # lives in deps.find_js_runtime(). None -> let yt-dlp use its default.
        self.js_runtimes: dict = (
            js_runtimes if js_runtimes is not None else {"deno": {}}
        )
        self._current_index = 0
        self._skipped = 0

    # ----------------------------- yt-dlp opts -----------------------------

    def _ydl_opts(self, *, archive: Archive | None = None, quiet: bool = True) -> dict:
        fmt = self.profile.format
        embed_meta = bool(self.profile.embed_metadata)
        embed_thumb = bool(self.profile.embed_thumbnail)

        # Postprocessors must be built exactly like yt-dlp's CLI does
        # (yt_dlp/__init__.py get_postprocessors): the CLI-only flags
        # embedmetadata/embedthumbnail/sponsorblock_remove are NOT accepted as
        # YoutubeDL params and are silently ignored when passed raw.
        postprocessors: list[dict] = []
        if self.profile.sponsorblock:
            postprocessors.append(
                {
                    "key": "SponsorBlock",
                    "categories": {"sponsor", "selfpromo", "interaction"},
                    "api": "https://sponsor.ajay.app",
                    "when": "after_filter",
                }
            )

        if fmt in ("flac", "wav"):
            opts_format = "bestaudio/best"
            postprocessors.append(
                {"key": "FFmpegExtractAudio", "preferredcodec": fmt, "preferredquality": "0"}
            )
        elif fmt == "opus":
            opts_format = "bestaudio[acodec=opus]/bestaudio/best"
            postprocessors.append(
                {"key": "FFmpegExtractAudio", "preferredcodec": "opus"}
            )
        elif fmt == "m4a":
            opts_format = "bestaudio[ext=m4a]/bestaudio/best"
            postprocessors.append(
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
            )
        else:  # mp3
            opts_format = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(self.profile.bitrate).rstrip("Kk"),
                }
            )

        if self.profile.sponsorblock:
            postprocessors.append(
                {
                    "key": "ModifyChapters",
                    "remove_sponsor_segments": {"sponsor", "selfpromo", "interaction"},
                    "remove_chapters_patterns": set(),
                    "remove_ranges": set(),
                    "sponsorblock_chapter_title": "[SponsorBlock]: %(category_names)l",
                    "force_keyframes": False,
                }
            )

        if embed_meta:
            postprocessors.append(
                {
                    "key": "FFmpegMetadata",
                    "add_chapters": False,
                    "add_metadata": True,
                    "add_infojson": False,
                }
            )
        if embed_thumb:
            postprocessors.append(
                {"key": "EmbedThumbnail", "already_have_thumbnail": False}
            )

        opts: dict = {
            "quiet": quiet,
            "no_warnings": False,
            "noplaylist": False,
            # per-entry downloads run one video at a time: let errors surface so
            # failed songs are NOT recorded as successes (a bad run used to add
            # them to the archive forever). fetch_info overrides this to True.
            "ignoreerrors": False,
            "retries": 1,  # we do our own retry loop with better reporting
            "fragment_retries": 3,
            "file_access_retries": 3,
            "continuedl": True,
            "windowsfilenames": True,
            "concurrent_fragment_downloads": 4,
            "noprogress": True,  # our hooks draw progress; avoid double output
            "writethumbnail": embed_thumb,  # EmbedThumbnailPP deletes it after use
            "matchfilter": None,
            "format": opts_format,
            "postprocessors": postprocessors,
            "logger": _YDLLogger(self.hooks),
            "js_runtimes": dict(self.js_runtimes),
        }

        if self.ffmpeg_location:
            opts["ffmpeg_location"] = self.ffmpeg_location
        if archive is not None:
            opts["download_archive"] = str(archive.path)
        if self.proxy:
            opts["proxy"] = self.proxy
        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = ("chrome",)
        return opts

    # ------------------------------ fetch info -----------------------------

    def fetch_info(self, url: str) -> dict:
        """Read playlist metadata WITHOUT downloading."""
        import yt_dlp

        self.hooks.on_progress(Progress(phase="fetching", message="Reading playlist..."))
        opts = self._ydl_opts(quiet=True)
        # metadata-only pass: never touch the disk; tolerate unavailable videos
        opts.update(
            {
                "extract_flat": True,
                "skip_download": True,
                "ignoreerrors": True,
                "writethumbnail": False,
                "writeinfojson": False,
                "postprocessors": [],
            }
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("could not read playlist info (check the URL)")
        if info.get("_type") not in ("playlist", "multi_video") and "entries" not in info:
            # single video passed instead of a playlist
            info = {
                "_type": "playlist",
                "title": info.get("title") or "YT_Video",
                "entries": [info],
                "webpage_url": url,
            }
        return info

    # -------------------------------- run ----------------------------------

    def run(self, url: str, dest_root: Path) -> Report:
        """Download everything in ``url`` into ``dest_root/<playlist title>/``."""
        info = self.fetch_info(url)
        title = info.get("title") or info.get("playlist_title") or "YT_Playlist"
        entries = [e for e in (info.get("entries") or []) if e]

        session = PlaylistSession(dest_root, title)
        report = Report(playlist_title=title, out_dir=session.folder)
        total = len(entries)

        self.hooks.on_log(f"Playlist: {title} ({total} entries)")
        self.hooks.on_log(f"Saving to: {session.folder}")

        if total == 0:
            self.hooks.on_log("Playlist is empty (or private).")
            return report

        opts = self._ydl_opts(archive=session.archive)

        self._current_index = 0
        self._skipped = 0

        def progress_hook(d: dict) -> None:
            self.cancel.interrupt()
            status = d.get("status")
            if status == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                pct = (done * 100.0 / total_bytes) if total_bytes else 0.0
                phase = "downloading"
            elif status in ("finished", "completed"):
                pct, phase = 100.0, "postprocessing"
            else:
                pct, phase = 0.0, "downloading"
            self.hooks.on_progress(
                Progress(
                    index=self._current_index,
                    total=total,
                    title=self._current_title,
                    phase=phase,
                    percent=pct,
                    skipped=self._skipped,
                )
            )

        def postprocessor_hook(d: dict) -> None:
            self.cancel.interrupt()

        opts["progress_hooks"] = [progress_hook]
        opts["postprocessor_hooks"] = [postprocessor_hook]

        self._current_title = ""

        for i, entry in enumerate(entries, start=1):
            if self.cancel.cancelled:
                report.cancelled = True
                break

            self._current_index = i
            entry_url = self._entry_url(entry)
            entry_title = entry.get("title") or entry_url or f"entry {i}"
            self._current_title = entry_title

            # already downloaded? (archive lookup, no network)
            vid = self._entry_id(entry)
            extractor = (
                entry.get("extractor_key") or entry.get("ie_key") or "youtube"
            ).lower()
            archive_key = f"{extractor} {vid}" if vid else None
            if archive_key and archive_key in session.archive:
                self._skipped += 1
                report.skipped.append(entry_title)
                self.hooks.on_progress(
                    Progress(
                        index=i,
                        total=total,
                        title=entry_title,
                        phase="downloading",
                        percent=100.0,
                        skipped=self._skipped,
                        message="already downloaded",
                    )
                )
                continue

            if not entry_url:
                report.failed.append((entry_title, "no URL found"))
                session.failures.record(
                    playlist=title, url="", title=entry_title, error="no URL found"
                )
                continue

            # per-entry filename: we download entries one by one (no playlist
            # context), so %(playlist_index) would render as "NA"
            opts["outtmpl"] = str(session.folder / f"{i:03d} - %(title).120s.%(ext)s")

            error_msg, attempts = self._download_entry_with_retries(
                ydl_opts=opts, url=entry_url
            )
            if error_msg is None:
                report.ok.append(entry_title)
                if archive_key:
                    session.archive.add(archive_key)
            else:
                report.failed.append((entry_title, error_msg))
                session.failures.record(
                    playlist=title,
                    url=entry_url,
                    title=entry_title,
                    error=error_msg,
                    attempts=attempts,
                )
                self.hooks.on_log(f"FAILED: {entry_title} -> {error_msg}")

        session.archive.save()
        if self.cancel.cancelled:
            report.cancelled = True
        return report

    # ------------------------------ helpers --------------------------------

    def _download_entry_with_retries(
        self, *, ydl_opts: dict, url: str
    ) -> tuple[str | None, int]:
        """Download one entry. Returns (error_message | None, attempts)."""
        import yt_dlp

        attempts = 0
        last_error = "unknown error"
        while attempts <= self.retries:
            attempts += 1
            if self.cancel.cancelled:
                return "cancelled", attempts
            try:
                opts = dict(ydl_opts)
                opts["noplaylist"] = True
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                return None, attempts
            except (KeyboardInterrupt, InterruptedError):
                raise
            except Exception as exc:  # yt_dlp.utils.DownloadError et al.
                msg = str(exc) or exc.__class__.__name__
                last_error = msg
                if not is_transient_error(msg):
                    return msg, attempts
                if attempts <= self.retries:
                    delay = 2**attempts
                    self.hooks.on_log(
                        f"Transient error, retrying in {delay}s: {msg[:120]}"
                    )
                    time.sleep(delay)
        return last_error, attempts

    @staticmethod
    def _entry_url(entry: dict) -> str:
        vid = entry.get("id")
        ie = (entry.get("ie_key") or entry.get("extractor_key") or "").lower()
        # full video info dicts also carry a "url", but it can be the raw
        # stream URL (…/videoplayback) -> prefer the canonical watch URL
        if vid and ie.startswith("youtube"):
            return f"https://www.youtube.com/watch?v={vid}"
        if entry.get("url"):
            return str(entry["url"])
        if vid:
            return str(vid)
        return ""

    @staticmethod
    def _entry_id(entry: dict) -> str:
        if entry.get("id"):
            return str(entry["id"])
        url = entry.get("url") or ""
        if not url:
            return ""
        parsed = urlparse(str(url))
        if "youtube" in parsed.netloc:
            vid = parse_qs(parsed.query).get("v")
            if vid:
                return vid[0]
            parts = parsed.path.strip("/").split("/")
            if parts and parts[-1] not in ("watch", "list"):
                return parts[-1]
        return str(url).rstrip("/").rsplit("/", 1)[-1]
