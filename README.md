# YT Playlist Audio Downloader

A lightweight script to download YouTube and YouTube Music playlists in multiple audio formats, compatible with Linux and Termux.

## Quick Start

Download the latest release directly:

```
bash <(curl -sSL https://github.com/laopro/list2audioxd/releases/latest/download/yt-audio-downloader-linux-termux.sh)
```

Features
Works on Linux and Termux (experimental).

Downloads full playlists from YouTube and YouTube Music.

Supported audio formats: M4A, MP3, OPUS, FLAC.

Downloads without extra compression, keeping original quality.

Creates a folder for each playlist and adds new songs if the folder already exists.

Requirements
yt-dlp executable in your system PATH.

ffmpeg for audio processing.

In Termux, install dependencies:

pkg update && pkg upgrade
pkg install ffmpeg
termux-setup-storage
Download yt-dlp directly:

```
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/bin/yt-dlp
chmod +x ~/bin/yt-dlp
```

Usage
Run the script:

```
./yt-playlist-audio-downloader.sh
```

Select the download folder.

Paste the YouTube or YouTube Music playlist URL.

The script will download all songs into the corresponding playlist folder.

Notes
If a playlist folder already exists, only new songs will be downloaded.

On Termux, make sure storage is configured with termux-setup-storage.
