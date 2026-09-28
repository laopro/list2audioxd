"""State module tests: archive, failures, playlist session."""

import json

from list2audio.config import sanitize_name
from list2audio.state import Archive, FailureLog, PlaylistSession


def test_sanitize_name_windows_forbidden_chars():
    assert "/" not in sanitize_name('a/b:c*d?e"f<g>h|i')
    assert "\\" not in sanitize_name("a\\b")
    assert sanitize_name("   ") == "YT_Playlist"
    assert sanitize_name("") == "YT_Playlist"


def test_sanitize_name_truncates():
    assert len(sanitize_name("x" * 500)) <= 150


def test_archive_add_contains_dedup(tmp_path):
    arch = Archive(tmp_path / "archive.txt")
    assert "youtube abc" not in arch
    arch.add("youtube abc")
    arch.add("youtube abc")  # duplicate ignored
    assert "youtube abc" in arch
    assert len(arch) == 1


def test_archive_persists(tmp_path):
    path = tmp_path / "archive.txt"
    a1 = Archive(path)
    a1.add("youtube aaa")
    a1.add("youtube bbb")
    a1.save()

    a2 = Archive(path)
    assert "youtube aaa" in a2
    assert "youtube bbb" in a2
    assert len(a2) == 2


def test_archive_append_is_visible_without_save(tmp_path):
    path = tmp_path / "archive.txt"
    a1 = Archive(path)
    a1.add("youtube ccc")
    # append already hit the disk -> a fresh reader sees it
    a2 = Archive(path)
    assert "youtube ccc" in a2


def test_archive_corrupt_file_starts_fresh(tmp_path):
    path = tmp_path / "archive.txt"
    path.write_bytes(b"\xff\xfe\x00garbage")
    arch = Archive(path)
    assert len(arch) == 0
    arch.add("youtube ok")
    assert "youtube ok" in arch


def test_failure_log_roundtrip(tmp_path):
    log = FailureLog(tmp_path / "failures.jsonl")
    log.record(playlist="P", url="https://x", title="Song", error="private", attempts=3)
    log.record(playlist="P", url="https://y", title="Song2", error="404")
    rows = log.read_all()
    assert len(rows) == 2
    assert rows[0]["title"] == "Song"
    assert rows[0]["attempts"] == 3
    assert rows[1].get("attempts", 1) == 1


def test_failure_log_bad_lines_skipped(tmp_path):
    path = tmp_path / "failures.jsonl"
    path.write_text("not json\n" + json.dumps({"title": "ok"}) + "\n", encoding="utf-8")
    rows = FailureLog(path).read_all()
    assert len(rows) == 1


def test_playlist_session_layout(tmp_path):
    sess = PlaylistSession(tmp_path, "My: Playlist/Name")
    assert sess.folder.exists()
    assert sess.folder.parent == tmp_path
    assert ":" not in sess.folder.name
    assert "/" not in sess.folder.name
    assert sess.archive.path == sess.folder / "download_archive.txt"
