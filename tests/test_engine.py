"""Engine tests (network-free): error classification, entry parsing, report."""

from pathlib import Path

import pytest

from list2audio.engine import (
    CancelToken,
    Engine,
    Progress,
    Report,
    is_transient_error,
)
from list2audio.profiles import UNIVERSAL

# --------------------------- error classification ---------------------------


def test_transient_network_errors():
    assert is_transient_error("URLError: timed out")
    assert is_transient_error("HTTP Error 503: Service Unavailable")
    assert is_transient_error("HTTP Error 429: Too Many Requests")
    assert is_transient_error("Connection reset by peer")


def test_permanent_errors_not_transient():
    assert not is_transient_error("Video unavailable")
    assert not is_transient_error("Private video")
    assert not is_transient_error("HTTP Error 404: Not Found")


# -------------------------------- entry parsing ------------------------------


def test_entry_url_from_id():
    entry = {"id": "abc123", "ie_key": "Youtube"}
    assert Engine._entry_url(entry) == "https://www.youtube.com/watch?v=abc123"


def test_entry_url_passthrough():
    entry = {"url": "https://example.com/v/1"}
    assert Engine._entry_url(entry) == "https://example.com/v/1"


def test_entry_id_from_url():
    entry = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    assert Engine._entry_id(entry) == "dQw4w9WgXcQ"


def test_entry_id_direct():
    assert Engine._entry_id({"id": "xyz"}) == "xyz"


def test_entry_empty():
    assert Engine._entry_url({}) == ""
    assert Engine._entry_id({}) == ""


# --------------------------------- report -----------------------------------


def test_report_counts():
    r = Report(playlist_title="p", out_dir=Path("."))
    r.ok.append("a")
    r.ok.append("b")
    r.skipped.append("c")
    r.failed.append(("d", "boom"))
    assert r.total == 4
    assert r.success is False


def test_report_success_when_only_ok_and_skipped():
    r = Report()
    r.ok.append("a")
    r.skipped.append("b")
    assert r.success is True


def test_report_cancelled_not_success():
    r = Report()
    r.ok.append("a")
    r.cancelled = True
    assert r.success is False


# --------------------------------- progress ---------------------------------


def test_progress_overall_percent():
    p = Progress(index=5, total=10, percent=50)
    assert p.overall_percent == pytest.approx(45.0)


def test_progress_overall_percent_bounds():
    assert Progress(index=0, total=0, percent=0).overall_percent == 0.0
    assert Progress(index=10, total=10, percent=100).overall_percent == 100.0


def test_progress_clamped():
    assert Progress(index=99, total=10, percent=100).overall_percent == 100.0


# ------------------------------- cancel token --------------------------------


def test_cancel_token():
    tok = CancelToken()
    assert not tok.cancelled
    tok.cancel()
    assert tok.cancelled
    with pytest.raises(KeyboardInterrupt):
        tok.interrupt()


def test_engine_rejects_bad_profile():
    from list2audio.profiles import custom_profile

    with pytest.raises(ValueError):
        Engine(custom_profile(format="mp3", bitrate="5000"))


def test_engine_accepts_universal():
    e = Engine(UNIVERSAL, retries=0)
    assert e.profile.key == "universal"


def test_ydl_opts_mp3_profile():
    e = Engine(UNIVERSAL)
    opts = e._ydl_opts()
    pps = opts["postprocessors"]
    assert pps[0]["key"] == "FFmpegExtractAudio"
    assert pps[0]["preferredcodec"] == "mp3"
    assert pps[0]["preferredquality"] == "192"


def test_ydl_opts_embeds_metadata_and_thumbnail():
    opts = Engine(UNIVERSAL)._ydl_opts()
    keys = [pp["key"] for pp in opts["postprocessors"]]
    # order matters: extract audio -> metadata -> thumbnail (yt-dlp CLI order)
    assert keys == ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]
    # thumbnail is written to disk so EmbedThumbnailPP can consume it...
    assert opts["writethumbnail"] is True
    # ...and deleted after embedding (no stray .webp files in the folder)
    thumb_pp = opts["postprocessors"][keys.index("EmbedThumbnail")]
    assert thumb_pp["already_have_thumbnail"] is False


def test_ydl_opts_light_profile_no_embeds():
    from list2audio.profiles import LIGHT

    opts = Engine(LIGHT)._ydl_opts()
    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "FFmpegMetadata" not in keys
    assert "EmbedThumbnail" not in keys
    assert opts["writethumbnail"] is False


def test_ydl_opts_no_cli_only_params():
    """embedthumbnail/embedmetadata/sponsorblock_remove are CLI flags, not
    YoutubeDL params: passing them raw is silently ignored by yt-dlp."""
    opts = Engine(UNIVERSAL)._ydl_opts()
    for bogus in ("embedthumbnail", "embedmetadata", "addmetadata", "sponsorblock_remove"):
        assert bogus not in opts


def test_ydl_opts_download_does_not_ignore_errors():
    """Failures must raise so failed songs never enter the archive."""
    assert Engine(UNIVERSAL)._ydl_opts()["ignoreerrors"] is False


def test_fetch_opts_tolerates_errors():
    opts = Engine(UNIVERSAL)._ydl_opts()
    # fetch_info overrides these (flat listing must skip unavailable videos)
    opts.update({"extract_flat": True, "skip_download": True, "ignoreerrors": True})
    assert opts["ignoreerrors"] is True


def test_ydl_opts_js_runtimes_passed():
    e = Engine(UNIVERSAL, js_runtimes={"node": {}})
    assert e._ydl_opts()["js_runtimes"] == {"node": {}}


def test_ydl_opts_has_deduped_logger():
    class Hooks:
        def __init__(self):
            self.messages = []

        def on_progress(self, progress):
            pass

        def on_log(self, message):
            self.messages.append(message)

    from list2audio.engine import _YDLLogger

    h = Hooks()
    log = _YDLLogger(h)
    log.debug("noise")
    log.info("noise")
    log.warning("warn once")
    log.warning("warn once")  # duplicate dropped
    log.error("real error")
    assert h.messages == ["warn once", "real error"]
    assert Engine(UNIVERSAL)._ydl_opts()["logger"] is not None


def test_ydl_opts_no_archive_by_default():
    opts = Engine(UNIVERSAL)._ydl_opts()
    assert "download_archive" not in opts
