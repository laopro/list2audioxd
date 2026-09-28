"""Profile logic tests."""

import pytest

from list2audio.profiles import (
    AUDIO_FORMATS,
    DEFAULT_PROFILE,
    FULL,
    LIGHT,
    UNIVERSAL,
    custom_profile,
    get_profile,
)


def test_profiles_exist_and_distinct():
    assert {p.key for p in (LIGHT, UNIVERSAL, FULL)} == {"light", "universal", "full"}
    formats = {p.format for p in (LIGHT, UNIVERSAL, FULL)}
    assert formats == {"opus", "mp3", "flac"}


def test_default_profile_is_universal():
    assert DEFAULT_PROFILE.key == "universal"
    assert DEFAULT_PROFILE.embed_metadata is True


def test_get_profile_case_insensitive():
    assert get_profile("LIGHT") is LIGHT
    assert get_profile("Full") is FULL


def test_get_profile_unknown_raises():
    with pytest.raises(KeyError):
        get_profile("nope")


def test_custom_profile_lossless_disables_metadata():
    p = custom_profile(format="flac", embed_metadata=True, embed_thumbnail=True)
    assert p.lossless is True
    assert p.embed_metadata is False
    assert p.embed_thumbnail is False


def test_custom_profile_bitrate_validation():
    with pytest.raises(ValueError):
        custom_profile(format="mp3", bitrate="9999")


def test_custom_profile_valid_bitrates():
    for br in ("128", "192", "320"):
        p = custom_profile(format="mp3", bitrate=br)
        p.validate()


def test_all_formats_accepted():
    for fmt in AUDIO_FORMATS:
        custom_profile(format=fmt, bitrate="192").validate()
