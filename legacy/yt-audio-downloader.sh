#!/usr/bin/env bash

# ================= UI =================
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

trap "echo -e '\n${RED}Interrupted by user.${NC}'; exit" INT

# ================= Header =================
clear
echo -e "yt/ytm audio playlist downloader by \e]8;;https://github.com/laopro\a\e[36m@laopro\e[0m\e]8;;\a"
echo

# ================= Dependency check =================
MISSING=()

command -v yt-dlp >/dev/null 2>&1 || MISSING+=("yt-dlp")
command -v ffmpeg >/dev/null 2>&1 || MISSING+=("ffmpeg")

if [ "${#MISSING[@]}" -ne 0 ]; then
    echo -e "${RED}Missing required dependencies:${NC}"
    for d in "${MISSING[@]}"; do
        echo " - $d"
    done
    echo
    echo "Install them manually and rerun the script."
    exit 1
fi

HAS_ZENITY=false
command -v zenity >/dev/null 2>&1 && HAS_ZENITY=true

echo -e "${GREEN}System check passed.${NC}"
echo

# ================= Warning =================
echo -e "${YELLOW}Warning${NC}"
echo "This is an unofficial script."
echo "You run it at your own risk."
echo
read -rp "Continue? [Y/n]: " ACK
[[ "$ACK" =~ ^[Nn]$ ]] && exit 0

clear
echo -e "yt/ytm audio playlist downloader by \e]8;;https://github.com/laopro\a\e[36m@laopro\e[0m\e]8;;\a"
echo

# ================= Download location =================
echo -e "${CYAN}Download location${NC}"

if $HAS_ZENITY; then
    echo "1) Select folder visually (recommended)"
    echo "2) Enter path manually"
    read -rp "Selection [1]: " LOC
    LOC=${LOC:-1}
else
    echo "Zenity not found → visual picker disabled"
    echo "1) Enter path manually"
    LOC=1
fi

LOC=${LOC//[^0-9]/}
LOC=${LOC:-1}

if [[ "$LOC" == "1" && "$HAS_ZENITY" == true ]]; then
    DEST=$(zenity --file-selection --directory --title="Select download folder")
else
    read -rp "Path: " DEST
fi

[[ -z "$DEST" ]] && exit 1
mkdir -p "$DEST" || exit 1

# ================= Playlist =================
echo
read -rp "Paste playlist URL: " URL
[[ -z "$URL" ]] && exit 1

echo
echo "Reading playlist information..."

PLAYLIST_TITLE=$(yt-dlp --flat-playlist --print "%(playlist_title)s" "$URL" 2>/dev/null | head -n1)
PLAYLIST_TITLE=${PLAYLIST_TITLE:-YT_Playlist}
PLAYLIST_TITLE=$(echo "$PLAYLIST_TITLE" | tr '/:*?"<>|' '_')

OUT="$DEST/$PLAYLIST_TITLE"
mkdir -p "$OUT"

# ================= Profiles =================
echo
echo -e "${CYAN}Audio profiles${NC}"
echo
echo "1) Light"
echo "   • Opus 128 kbps"
echo "   • Smallest size"
echo "   • No metadata, no thumbnail"
echo
echo "2) Universal"
echo "   • MP3 192 kbps (recommended)"
echo "   • High compatibility"
echo "   • Metadata + embedded thumbnail"
echo
echo "3) Full"
echo "   • FLAC (lossless)"
echo "   • Maximum quality"
echo "   • No metadata, no thumbnail"
echo
echo "4) Custom"
echo "   • Fully configurable"
echo

read -rp "Select profile [1]: " PROFILE
PROFILE=${PROFILE//[^0-9]/}
PROFILE=${PROFILE:-1}

FORMAT=""
QUALITY=""
META=false
THUMB=false
PROFILE_NAME=""

# ================= Profile logic =================
case "$PROFILE" in
1)
    PROFILE_NAME="Light"
    FORMAT="opus"
    QUALITY="128K"
    ;;
2)
    PROFILE_NAME="Universal"
    FORMAT="mp3"
    QUALITY="192K"
    META=true
    THUMB=true
    ;;
3)
    PROFILE_NAME="Full"
    FORMAT="flac"
    QUALITY="lossless"
    ;;
4)
    PROFILE_NAME="Custom"

    echo
    echo "Select audio format:"
    echo "1) MP3   – Universal compatibility (recommended)"
    echo "2) M4A   – Better quality than MP3"
    echo "3) Opus  – Small size"
    echo "4) FLAC  – Lossless"
    echo "5) WAV   – Uncompressed (very large)"
    read -rp "Format [1]: " FMT
    FMT=${FMT//[^0-9]/}
    FMT=${FMT:-1}

    case "$FMT" in
        1) FORMAT="mp3" ;;
        2) FORMAT="m4a" ;;
        3) FORMAT="opus" ;;
        4) FORMAT="flac" ;;
        5) FORMAT="wav" ;;
    esac

    echo
    echo "Select quality:"
    echo "1) 128K      – Small size"
    echo "2) 192K      – Balanced (recommended)"
    echo "3) 320K      – High quality"
    echo "4) Lossless  – No compression"
    read -rp "Quality [2]: " Q
    Q=${Q//[^0-9]/}
    Q=${Q:-2}

    case "$Q" in
        1) QUALITY="128K" ;;
        2) QUALITY="192K" ;;
        3) QUALITY="320K" ;;
        4) QUALITY="lossless" ;;
    esac

    read -rp "Embed metadata? [y/N] (recommended): " M
    [[ "$M" =~ ^[Yy]$ ]] && META=true

    read -rp "Embed thumbnail? [y/N] (recommended): " T
    [[ "$T" =~ ^[Yy]$ ]] && THUMB=true

    if [[ ("$FORMAT" == "flac" || "$FORMAT" == "wav") && ("$META" == true || "$THUMB" == true) ]]; then
        echo
        echo -e "${YELLOW}Notice${NC}"
        echo "Metadata and thumbnails for FLAC/WAV require Python mutagen."
        echo "They will be disabled to avoid errors."
        META=false
        THUMB=false
    fi
    ;;
*)
    exit 1
    ;;
esac

# ================= Summary =================
echo
echo "Summary"
echo "Playlist : $PLAYLIST_TITLE"
echo "Output   : $OUT"
echo "Profile  : $PROFILE_NAME"

if [[ "$PROFILE_NAME" == "Custom" ]]; then
    echo
    echo "Format     : $FORMAT"
    echo "Quality    : $QUALITY"
    echo "Metadata   : $META"
    echo "Thumbnail  : $THUMB"
fi

echo
read -rp "Start download now? [Y/n]: " GO
[[ "$GO" =~ ^[Nn]$ ]] && exit 0

echo
echo "Starting download..."

# ================= yt-dlp args =================
ARGS=()
ARGS+=("-o" "$OUT/%(title).200s.%(ext)s")

case "$FORMAT" in
opus)
    ARGS+=("-f" "bestaudio[acodec=opus]/bestaudio")
    ;;
m4a)
    ARGS+=("-f" "bestaudio[ext=m4a]/bestaudio")
    ;;
mp3)
    ARGS+=("-x" "--audio-format" "mp3" "--audio-quality" "${QUALITY%K}")
    ;;
flac)
    ARGS+=("-x" "--audio-format" "flac")
    ;;
wav)
    ARGS+=("-x" "--audio-format" "wav")
    ;;
esac

$META && ARGS+=("--embed-metadata")
$THUMB && ARGS+=("--embed-thumbnail")

yt-dlp "${ARGS[@]}" "$URL"

echo
echo -e "${GREEN}Finished.${NC}"
echo "Location: $OUT"