"""Build dist/list2audio.py: single-file app (zipapp) for `python list2audio.py`.

Bundles our package + runtime deps (yt-dlp, mutagen) so anyone with a stock
Python 3.10+ can run it with no install step. CLI only (no GUI/tkinter needed).

Usage:  python packaging/build_zipapp.py
Output: dist/list2audio.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "list2audio"
DIST = ROOT / "dist"
OUT = DIST / "list2audio.py"
STAGE = ROOT / "build" / "zipapp"

# runtime deps the CLI needs (customtkinter/tkinter NOT needed: CLI only)
DEPS = ["yt-dlp>=2024.4.9", "mutagen>=1.47"]

MAIN = "from list2audio.cli import main\nraise SystemExit(main())\n"


def main() -> int:
    if not SRC.is_dir():
        print(f"error: package dir not found: {SRC}")
        return 1

    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "list2audio").mkdir(parents=True)

    for src_file in SRC.rglob("*.py"):
        if "__pycache__" in src_file.parts:
            continue
        dest = STAGE / "list2audio" / src_file.relative_to(SRC)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
    (STAGE / "__main__.py").write_text(MAIN, encoding="utf-8")

    print(f"vendoring deps: {', '.join(DEPS)} ...")
    proc = subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet",
            "--target", str(STAGE), *DEPS,
        ],
    )
    if proc.returncode != 0:
        return proc.returncode

    DIST.mkdir(exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    zipapp.create_archive(STAGE, OUT, interpreter="/usr/bin/env python3", compressed=True)

    size_mb = OUT.stat().st_size / 1_000_000
    print(f"OK: {OUT} ({size_mb:.1f} MB)")

    # smoke test: -S disables site-packages, so the bundle must be
    # self-contained (no installed deps leak in)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "-S", str(OUT), "--version"],
            capture_output=True, text=True, cwd=tmp,
        )
    print("smoke:", (proc.stdout or proc.stderr).strip())
    if proc.returncode != 0 or "list2audio" not in proc.stdout:
        print("error: zipapp smoke test failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
