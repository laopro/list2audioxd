"""Command line interface.

Usage:
    list2audio                       # interactive mode (wizard)
    list2audio <URL> [options]       # scriptable mode
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import default_dest, save_prefs
from .profiles import (
    AUDIO_FORMATS,
    DEFAULT_PROFILE,
    PROFILES,
    Profile,
    custom_profile,
    get_profile,
)

# ------------------------------- colors ------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty()


class C:
    CYAN = "\033[0;36m" if _supports_color() else ""
    GREEN = "\033[0;32m" if _supports_color() else ""
    YELLOW = "\033[1;33m" if _supports_color() else ""
    RED = "\033[0;31m" if _supports_color() else ""
    DIM = "\033[2m" if _supports_color() else ""
    NC = "\033[0m" if _supports_color() else ""


def print_header() -> None:
    print(f"{C.CYAN}list2audio xd{C.NC}  v{__version__}  -  yt/ytm playlist downloader")
    print()


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130) from None
    return value or default


def ask_choice(prompt: str, valid: list[str], default: str) -> str:
    while True:
        value = ask(prompt, default).lower()
        if value in valid:
            return value
        print(f"{C.YELLOW}Please choose one of:{C.NC} {', '.join(valid)}")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = ask(f"{prompt} [{hint}]", "y" if default else "n").lower()
    if value in ("y", "yes"):
        return True
    if value in ("n", "no"):
        return False
    return default


# ------------------------------ interactive --------------------------------


class ConsoleHooks:
    """Renders engine progress on the terminal."""

    def __init__(self) -> None:
        self._last_len = 0

    def on_log(self, message: str) -> None:
        self._clear_line()
        print(message)

    def on_progress(self, p) -> None:
        if p.phase == "fetching":
            self._clear_line()
            print(f"{p.message}...")
            return
        if p.total <= 0:
            return
        bar_len = 24
        filled = int(bar_len * p.overall_percent / 100)
        bar = "#" * filled + "-" * (bar_len - filled)
        title = (p.title or "")[:48]
        line = (
            f"[{bar}] {p.index}/{p.total} {p.percent:3.0f}%  {title}"
            + (f" ({p.message})" if p.message else "")
        )
        self._write_line(line)

    def _write_line(self, line: str) -> None:
        sys.stdout.write("\r" + line.ljust(self._last_len)[:200])
        sys.stdout.flush()
        self._last_len = len(line)

    def _clear_line(self) -> None:
        if self._last_len:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
            sys.stdout.flush()
            self._last_len = 0


def interactive_profile() -> Profile:
    print(f"{C.CYAN}Audio profiles{C.NC}")
    print()
    keys = list(PROFILES)
    for n, key in enumerate(keys, start=1):
        p = PROFILES[key]
        print(f"{n}) {p.name:<10} {p.description}")
    print(f"{len(keys) + 1}) Custom     Pick format / quality yourself")
    print()

    valid = [str(n) for n in range(1, len(keys) + 2)]
    choice = ask_choice("Select profile", valid, default="2")

    if int(choice) <= len(keys):
        return PROFILES[keys[int(choice) - 1]]

    print()
    print("Formats: " + ", ".join(AUDIO_FORMATS))
    fmt = ask_choice("Format", list(AUDIO_FORMATS), default="mp3")

    print("Quality: 1) 128K  2) 192K  3) 320K")
    q = ask_choice("Quality", ["1", "2", "3"], default="2")
    bitrate = {"1": "128", "2": "192", "3": "320"}[q]

    meta = ask_yes_no("Embed metadata", default=True)
    thumb = ask_yes_no("Embed thumbnail", default=True)
    if fmt in ("flac", "wav") and (meta or thumb):
        print(
            f"{C.YELLOW}Note:{C.NC} FLAC/WAV metadata+cover needs 'pip install mutagen',"
            " disabling for safety."
        )
        meta = thumb = False
    sb = ask_yes_no("Remove sponsor segments (SponsorBlock)", default=False)
    return custom_profile(
        format=fmt,
        bitrate=bitrate,
        embed_metadata=meta,
        embed_thumbnail=thumb,
        sponsorblock=sb,
    )


def run_interactive(url: str | None, dest: Path | None, profile: Profile | None) -> int:
    from .deps import DependencyError, ensure_all, self_update_yt_dlp
    from .engine import Engine, Report

    print_header()

    print(f"{C.YELLOW}Warning:{C.NC} unofficial tool, use at your own risk"
          " (personal use may violate YouTube ToS).")
    if not ask_yes_no("Continue", default=True):
        return 0
    print()

    # dependencies ----------------------------------------------------------
    print("Checking dependencies...")
    try:
        info = ensure_all(label=lambda m: print(f"  {m}"))
    except DependencyError as exc:
        print(f"{C.RED}Missing dependency:{C.NC}\n{exc}")
        return 1
    js_info = info.get("js") or {}
    js_label = next(iter(js_info), None)
    print(f"{C.GREEN}OK:{C.NC} yt-dlp {info['yt_dlp']}, ffmpeg found")
    if js_label:
        print(f"       JavaScript runtime: {js_label}")
    else:
        print(
            f"{C.YELLOW}Warning:{C.NC} no JS runtime (deno/node) found; "
            "YouTube downloads may fail."
        )
    self_update_yt_dlp(label=lambda m: print(f"  {m}"))
    print()

    # destination -----------------------------------------------------------
    if dest is None:
        default = str(default_dest())
        dest = Path(ask("Download folder", default=default))
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"{C.RED}Cannot create folder:{C.NC} {exc}")
        return 1

    # playlist url ----------------------------------------------------------
    if url is None:
        url = ask("Paste playlist URL")
        if not url:
            print("No URL given.")
            return 1

    # profile ---------------------------------------------------------------
    if profile is None:
        profile = interactive_profile()

    # summary ---------------------------------------------------------------
    print()
    print(f"{C.CYAN}Summary{C.NC}")
    print(f"  URL      : {url}")
    print(f"  Output   : {dest}")
    print(f"  Profile  : {profile.name} ({profile.description})")
    print()
    if not ask_yes_no("Start download", default=True):
        return 0
    print()

    # go --------------------------------------------------------------------
    hooks = ConsoleHooks()
    engine = Engine(
        profile,
        ffmpeg_path=info["ffmpeg"],
        js_runtimes=info["js"],
        hooks=hooks,
    )
    try:
        report: Report = engine.run(url, dest)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Interrupted.{C.NC}")
        return 130
    except Exception as exc:
        hooks._clear_line()
        print(f"{C.RED}Error:{C.NC} {exc}")
        return 1

    hooks._clear_line()
    print()
    if report.cancelled:
        print(f"{C.YELLOW}Cancelled.{C.NC} "
              f"({len(report.ok)} downloaded, {len(report.failed)} failed)")
    elif report.failed:
        print(f"{C.YELLOW}Finished with errors.{C.NC}")
        print(f"  downloaded : {len(report.ok)}")
        print(f"  skipped    : {len(report.skipped)} (already had)")
        print(f"  failed     : {len(report.failed)}")
        for title, err in report.failed[:10]:
            print(f"    - {title}: {err[:90]}")
        if len(report.failed) > 10:
            print(f"    ... and {len(report.failed) - 10} more "
                  f"(see {report.out_dir / 'failures.jsonl'})")
    else:
        print(f"{C.GREEN}Finished.{C.NC} {len(report.ok)} downloaded, "
              f"{len(report.skipped)} already had.")

    if report.out_dir:
        print(f"Location: {report.out_dir}")

    save_prefs(dest=str(dest), profile=profile.key)
    return 0 if not report.failed else 2


# ------------------------------ script mode --------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list2audio",
        description="Download YouTube / YouTube Music playlists as audio files.",
    )
    parser.add_argument("url", nargs="?", help="playlist URL (omit for interactive mode)")
    parser.add_argument("-d", "--dest", type=Path, help="output folder")
    parser.add_argument(
        "-p",
        "--profile",
        choices=sorted(PROFILES),
        help="audio profile (default: universal)",
    )
    parser.add_argument("-f", "--format", choices=AUDIO_FORMATS, help="override format")
    parser.add_argument("-q", "--bitrate", help="override bitrate, e.g. 320")
    parser.add_argument("--metadata", action="store_true", help="force-embed metadata")
    parser.add_argument("--no-metadata", action="store_true", help="skip metadata")
    parser.add_argument("--thumbnail", action="store_true", help="force-embed thumbnail")
    parser.add_argument("--no-thumbnail", action="store_true", help="skip thumbnail")
    parser.add_argument("--sponsorblock", action="store_true", help="remove sponsors")
    parser.add_argument("-y", "--yes", action="store_true", help="assume yes")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def profile_from_args(args: argparse.Namespace) -> Profile:
    base = get_profile(args.profile) if args.profile else DEFAULT_PROFILE
    if args.format is None and args.bitrate is None and not any(
        (args.metadata, args.no_metadata, args.thumbnail, args.no_thumbnail, args.sponsorblock)
    ):
        return base
    meta = base.embed_metadata
    thumb = base.embed_thumbnail
    if args.metadata:
        meta = True
    if args.no_metadata:
        meta = False
    if args.thumbnail:
        thumb = True
    if args.no_thumbnail:
        thumb = False
    fmt = args.format or base.format
    if fmt in ("flac", "wav"):
        meta = thumb = False
    return custom_profile(
        format=fmt,
        bitrate=args.bitrate or base.bitrate,
        embed_metadata=meta,
        embed_thumbnail=thumb,
        sponsorblock=base.sponsorblock or args.sponsorblock,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.url is None:
        # interactive: flags still pre-fill some decisions
        return run_interactive(
            url=None,
            dest=args.dest,
            profile=profile_from_args(args) if (
                args.format or args.profile or args.bitrate
            ) else None,
        )

    # non-interactive
    from .deps import DependencyError, ensure_all
    from .engine import Engine

    dest = args.dest or default_dest()
    profile = profile_from_args(args)
    try:
        info = ensure_all(label=lambda m: print(f"  {m}", file=sys.stderr))
    except DependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    hooks = ConsoleHooks()
    engine = Engine(
        profile,
        ffmpeg_path=info["ffmpeg"],
        js_runtimes=info["js"],
        hooks=hooks,
    )
    try:
        report = engine.run(args.url, dest)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        hooks._clear_line()
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        hooks._clear_line()

    save_prefs(dest=str(dest), profile=profile.key)

    if report.cancelled:
        return 130
    if report.failed:
        for title, err in report.failed:
            print(f"failed: {title} -> {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
