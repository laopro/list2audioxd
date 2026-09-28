# list2audio xd

Download YouTube / YouTube Music playlists as audio files — **for everyone, not just terminal people.**

```
┌──────────────────────────────────────────────┐
│  list2audio xd                              │
│                                              │
│  Playlist URL                                │
│  [ https://www.youtube.com/playlist?list=.. ]│
│                                              │
│  Save to: C:\Users\you\Music  [Browse]       │
│                                              │
│  Quality                                     │
│  [ Light ] [ Universal ] [ Full ] [ Custom ] │
│                                              │
│  [      Download playlist      ]             │
│  ██████████████████░░░░  37/50               │
│  Downloading: 14. Artist - Song              │
└──────────────────────────────────────────────┘
```

## Download (Windows)

1. Grab **`list2audio.exe`** from the [latest release](https://github.com/laopro/list2audioxd/releases/latest)
2. Double-click it
3. Paste a playlist link, pick a quality, hit **Download**

No Python, no terminal, no PATH tricks. ffmpeg is downloaded automatically on first run.

> First run may take a minute while it prepares ffmpeg + checks for yt-dlp updates.

## Features

- **GUI** — paste link, click, done
- **CLI too** — `list2audio <URL>` for scripts and power users
- Profiles: **Light** (opus, small), **Universal** (mp3 + metadata + cover), **Full** (flac), **Custom**
- **Incremental**: run it again later on the same playlist and it only grabs the new songs
- Failed songs don't kill the run — you get an honest report + `failures.jsonl`
- Automatic retries on network hiccups
- SponsorBlock support (remove sponsor segments)
- Cancel mid-download safely

## CLI usage

```bash
pip install -e .            # from a checkout
list2audio                          # interactive wizard
list2audio <URL>                    # defaults (universal/mp3)
list2audio <URL> -p light -d ~/Music
list2audio <URL> -f flac -y
list2audio <URL> -f mp3 -q 320 --sponsorblock
```

Run the GUI from source:

```bash
pip install -e .
list2audio-gui
```

Requirements: Python ≥ 3.10, `ffmpeg` (auto-provided on Windows).

## Project layout

```
src/list2audio/       core package
  engine.py           download engine (yt-dlp as a library)
  profiles.py         quality profiles
  cli.py              terminal interface
  gui/                desktop app (CustomTkinter)
  state.py            archive + failure log (incremental downloads)
  deps.py             yt-dlp / ffmpeg bootstrap
tests/                pytest suite
legacy/               the original Bash script (Linux/Termux)
packaging/            PyInstaller build
.github/workflows/    CI + release automation
```

## Legacy: Bash script (Linux / Termux)

The original single-file script still lives in [`legacy/`](legacy/) and works as before:

```bash
bash legacy/yt-audio-downloader.sh
```

Install deps first: `yt-dlp` + `ffmpeg` in your PATH.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
pyinstaller packaging/list2audio.spec   # build dist/list2audio.exe
```

Tag a release (`v2.x.y`) and GitHub Actions builds + publishes the `.exe` automatically.

## Roadmap

See [ROADMAP.md](ROADMAP.md) — Android (no Termux, via companion mode) is next after Windows is proven.

## Legal / fair use

This tool is for **personal use**. Downloading content from YouTube may violate YouTube's Terms of Service — you are responsible for how you use it. Don't redistribute copyrighted music. See YouTube ToS for details.

## License

[MIT](LICENSE)
