"""Audio quality profiles.

A profile is a declarative description of "what the user wants" (format,
bitrate, metadata...). The engine translates it into yt-dlp options, so the
GUI/CLI never build yt-dlp arguments themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

AUDIO_FORMATS = ("mp3", "m4a", "opus", "flac", "wav")

# File name template used for every download.
#   001 - Title.mp3  (ordered, stable, readable)
FILENAME_TEMPLATE = "%(playlist_index)03d - %(title).120s.%(ext)s"

# Maximum title length inside the template (Windows-friendly).
TITLE_MAX_LEN = 120


@dataclass(frozen=True)
class Profile:
    """Declarative download profile."""

    key: str
    name: str
    description: str
    format: str = "mp3"  # one of AUDIO_FORMATS
    bitrate: str = "192"  # kbps, ignored for lossless formats
    lossless: bool = False
    embed_metadata: bool = False
    embed_thumbnail: bool = False
    sponsorblock: bool = False

    @property
    def lossy(self) -> bool:
        return not self.lossless

    def validate(self) -> None:
        if self.format not in AUDIO_FORMATS:
            raise ValueError(f"unsupported format: {self.format!r}")
        if self.lossy and self.format in ("mp3", "m4a", "opus"):
            try:
                kbps = int(str(self.bitrate).rstrip("Kk"))
            except ValueError as exc:
                raise ValueError(f"invalid bitrate: {self.bitrate!r}") from exc
            if not 32 <= kbps <= 320:
                raise ValueError(f"bitrate out of range: {kbps}")


LIGHT = Profile(
    key="light",
    name="Light",
    description="Opus 128 kbps - smallest size, no metadata",
    format="opus",
    bitrate="128",
    lossless=False,
    embed_metadata=False,
    embed_thumbnail=False,
)

UNIVERSAL = Profile(
    key="universal",
    name="Universal",
    description="MP3 192 kbps - plays everywhere, metadata + cover art",
    format="mp3",
    bitrate="192",
    lossless=False,
    embed_metadata=True,
    embed_thumbnail=True,
)

FULL = Profile(
    key="full",
    name="Full",
    description="FLAC - lossless, maximum quality, big files",
    format="flac",
    bitrate="lossless",
    lossless=True,
    embed_metadata=True,
    embed_thumbnail=True,
)

PROFILES: dict[str, Profile] = {
    p.key: p for p in (LIGHT, UNIVERSAL, FULL)
}

DEFAULT_PROFILE = UNIVERSAL


def get_profile(key: str) -> Profile:
    """Return a profile by key (case-insensitive) or raise KeyError."""
    try:
        return PROFILES[key.lower()]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(f"unknown profile {key!r} (available: {known})") from None


def custom_profile(
    format: str = "mp3",
    bitrate: str = "192",
    embed_metadata: bool = False,
    embed_thumbnail: bool = False,
    sponsorblock: bool = False,
) -> Profile:
    """Build and validate a user-defined profile."""
    lossless = format in ("flac", "wav")
    profile = Profile(
        key="custom",
        name="Custom",
        description="User defined",
        format=format,
        bitrate="lossless" if lossless else bitrate,
        lossless=lossless,
        embed_metadata=embed_metadata and not lossless,
        embed_thumbnail=embed_thumbnail and not lossless,
        sponsorblock=sponsorblock,
    )
    profile.validate()
    return profile
