"""CLI argument handling tests (no network)."""

from pathlib import Path

import pytest

from list2audio.cli import build_parser, main, profile_from_args
from list2audio.config import sanitize_name
from list2audio.profiles import custom_profile


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.url is None
    assert args.dest is None
    assert args.profile is None


def test_parser_full(tmp_path):
    dest = tmp_path / "out"
    args = build_parser().parse_args(
        ["https://x/playlist", "-d", str(dest), "-p", "light", "-y"]
    )
    assert args.url == "https://x/playlist"
    assert Path(args.dest) == dest
    assert args.profile == "light"
    assert args.yes is True


def test_profile_from_args_base():
    args = build_parser().parse_args([])
    p = profile_from_args(args)
    assert p.key == "universal"  # default


def test_profile_from_args_profile_choice():
    args = build_parser().parse_args(["-p", "light"])
    p = profile_from_args(args)
    assert p.key == "light"


def test_profile_from_args_override_format():
    args = build_parser().parse_args(["-p", "light", "-f", "mp3", "-q", "320"])
    p = profile_from_args(args)
    assert p.format == "mp3"
    assert p.bitrate == "320"


def test_profile_from_args_flac_kills_metadata():
    args = build_parser().parse_args(["-f", "flac", "--metadata", "--thumbnail"])
    p = profile_from_args(args)
    assert p.format == "flac"
    assert p.embed_metadata is False
    assert p.embed_thumbnail is False


def test_profile_from_args_no_metadata():
    args = build_parser().parse_args(["--no-metadata", "--no-thumbnail"])
    p = profile_from_args(args)
    assert p.embed_metadata is False
    assert p.embed_thumbnail is False


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "1.0.0" in capsys.readouterr().out


def test_main_no_url_runs_interactive_and_fails_gracefully(monkeypatch):
    """With no TTY input, interactive mode should exit non-zero, not crash."""
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code in (130, 1)


def test_sanitize_used_for_playlist_dirs():
    # regression guard: playlist titles must never escape their folder
    name = sanitize_name("../../etc/passwd")
    assert ".." not in name
    assert "/" not in name
    assert sanitize_name("..") not in ("..", ".")
    assert sanitize_name("...") not in ("...", "..", ".")


def test_custom_profile_helper_used_by_cli_is_consistent():
    p = custom_profile(format="opus", bitrate="128")
    assert p.format == "opus"
    assert p.lossless is False
