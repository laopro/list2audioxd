# Roadmap

## Done (v2.0)
- [x] Python rewrite: yt-dlp as a library (progress, retries, cancellation)
- [x] Incremental downloads via per-playlist download archive
- [x] Honest error reporting (`failures.jsonl`, no more fake "Finished.")
- [x] Quality profiles (Light / Universal / Full / Custom)
- [x] CLI (interactive + scriptable)
- [x] Windows desktop GUI (CustomTkinter)
- [x] Auto-provision ffmpeg on Windows
- [x] Tests (pytest) + CI (GitHub Actions) + automated `.exe` releases

## Next (v2.1)
- [ ] Prove the Windows `.exe` with real users / real playlists
- [ ] App icon + branding
- [ ] yt-dlp auto-update surfaced in the GUI (badge/notice)
- [ ] Playlist preview in GUI before downloading (title + song count)
- [ ] Download queue (paste several playlists)
- [ ] i18n: English / Spanish UI strings

## Later (v2.2+)
- [ ] **Android without Termux — "Companion mode"**
  - PC/NAS runs `list2audio serve` (tiny local web server)
  - Phone (browser / installable PWA) pastes the URL and controls downloads
  - No terminal, no Termux, no APK needed on the phone
- [ ] macOS app bundle (PyInstaller onedir + .app)
- [ ] Microsoft Store packaging (MSIX)
- [ ] Optional: Spotify/other sources, metadata editing, art lookup (MusicBrainz)

## Won't do (for now)
- Cloud/hosted downloads (cost + legal exposure)
- Wrapping Termux into an APK (fragile, huge, store policy issues)
