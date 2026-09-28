"""Desktop GUI (CustomTkinter).

One window, linear flow:
  paste URL -> pick destination + profile -> Download -> progress -> summary
"""

from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path

import customtkinter as ctk

from .. import __version__
from ..config import default_dest, load_prefs, save_prefs
from ..profiles import AUDIO_FORMATS, PROFILES, Profile, custom_profile, get_profile

THEME = {
    "bg": "#101418",
    "panel": "#161b22",
    "border": "#2a3138",
    "text": "#e6edf3",
    "dim": "#8b949e",
    "accent": "#2f81f7",
    "ok": "#3fb950",
    "warn": "#d29922",
    "err": "#f85149",
}

PROFILE_ORDER = ["light", "universal", "full", "custom"]


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.prefs = load_prefs()
        self.queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_token = None
        self.profile_key = self.prefs.get("profile", "universal")
        if self.profile_key not in PROFILE_ORDER:
            self.profile_key = "universal"
        self.custom_opts = {
            "format": self.prefs.get("format", "mp3"),
            "bitrate": self.prefs.get("bitrate", "192"),
            "embed_metadata": bool(self.prefs.get("embed_metadata", True)),
            "embed_thumbnail": bool(self.prefs.get("embed_thumbnail", True)),
            "sponsorblock": bool(self.prefs.get("sponsorblock", False)),
        }

        self.title(f"list2audio xd  v{__version__}")
        self.geometry("620x680")
        self.minsize(560, 620)
        self.configure(fg_color=THEME["bg"])

        if self.prefs.get("geometry"):
            try:
                self.geometry(self.prefs["geometry"])
            except Exception:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    # ------------------------------- UI ------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 18, "pady": 6}

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", **pad)
        ctk.CTkLabel(
            header, text="list2audio xd", font=ctk.CTkFont(size=22, weight="bold"),
            text_color=THEME["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=f"v{__version__}", font=ctk.CTkFont(size=12),
            text_color=THEME["dim"],
        ).pack(side="right", pady=(10, 0))

        # URL -----------------------------------------------------------------
        ctk.CTkLabel(
            self, text="Playlist URL (YouTube / YouTube Music)",
            text_color=THEME["dim"], anchor="w",
        ).pack(fill="x", **pad)
        self.url_entry = ctk.CTkEntry(
            self, placeholder_text="https://www.youtube.com/playlist?list=...",
            height=40,
        )
        self.url_entry.pack(fill="x", padx=18)
        self.url_entry.bind("<Control-Return>", lambda e: self.start_download())

        # Destination ---------------------------------------------------------
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", **pad)
        ctk.CTkLabel(row, text="Save to", text_color=THEME["dim"]).pack(side="left")
        self.dest_var = ctk.StringVar(value=str(default_dest()))
        self.dest_entry = ctk.CTkEntry(row, textvariable=self.dest_var, height=32)
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(10, 8))
        ctk.CTkButton(
            row, text="Browse", width=90, height=32, fg_color=THEME["panel"],
            border_width=1, border_color=THEME["border"], hover_color="#1f2630",
            command=self._pick_dest,
        ).pack(side="right")

        # Profiles ------------------------------------------------------------
        ctk.CTkLabel(
            self, text="Quality", text_color=THEME["dim"], anchor="w",
        ).pack(fill="x", padx=18, pady=(10, 0))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=4)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="p")
        self.profile_buttons: dict[str, ctk.CTkButton] = {}
        for i, key in enumerate(PROFILE_ORDER):
            prof = PROFILES.get(key)
            label = f"{prof.name}" if prof else "Custom"
            btn = ctk.CTkButton(
                grid,
                text=label,
                height=38,
                fg_color=THEME["panel"],
                border_width=1,
                border_color=THEME["border"],
                hover_color="#1f2630",
                text_color=THEME["text"],
                command=lambda k=key: self._select_profile(k),
            )
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            self.profile_buttons[key] = btn

        self.profile_desc = ctk.CTkLabel(
            self, text="", text_color=THEME["dim"], font=ctk.CTkFont(size=12),
            anchor="w", justify="left",
        )
        self.profile_desc.pack(fill="x", padx=18)

        # Custom options (hidden unless Custom) --------------------------------
        self.custom_frame = ctk.CTkFrame(self, fg_color=THEME["panel"])
        row1 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(row1, text="Format", text_color=THEME["dim"]).pack(side="left")
        self.fmt_var = ctk.StringVar(value=self.custom_opts["format"])
        ctk.CTkOptionMenu(
            row1, values=list(AUDIO_FORMATS), variable=self.fmt_var, width=110,
            command=lambda _v: self._sync_custom(),
        ).pack(side="right")
        ctk.CTkLabel(row1, text="Bitrate", text_color=THEME["dim"]).pack(
            side="left", padx=(18, 0)
        )
        self.br_var = ctk.StringVar(value=self.custom_opts["bitrate"])
        ctk.CTkOptionMenu(
            row1, values=["128", "192", "320"], variable=self.br_var, width=90,
            command=lambda _v: self._sync_custom(),
        ).pack(side="right", padx=(0, 0))

        row2 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(2, 8))
        self.meta_var = ctk.BooleanVar(value=self.custom_opts["embed_metadata"])
        self.thumb_var = ctk.BooleanVar(value=self.custom_opts["embed_thumbnail"])
        self.sb_var = ctk.BooleanVar(value=self.custom_opts["sponsorblock"])
        ctk.CTkCheckBox(
            row2, text="Metadata", variable=self.meta_var,
            command=self._sync_custom, fg_color=THEME["accent"],
        ).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(
            row2, text="Cover art", variable=self.thumb_var,
            command=self._sync_custom, fg_color=THEME["accent"],
        ).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(
            row2, text="Remove sponsors", variable=self.sb_var,
            command=self._sync_custom, fg_color=THEME["accent"],
        ).pack(side="left")

        # Buttons ---------------------------------------------------------------
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(14, 4))
        self.download_btn = ctk.CTkButton(
            btn_row, text="Download playlist", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=THEME["accent"], hover_color="#1f6feb",
            command=self.start_download,
        )
        self.download_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", height=44, width=110,
            fg_color=THEME["panel"], border_width=1, border_color=THEME["border"],
            hover_color="#2a1a1a", text_color=THEME["err"],
            state="disabled", command=self.cancel_download,
        )
        self.cancel_btn.pack(side="right", padx=(10, 0))

        # Progress --------------------------------------------------------------
        self.progress = ctk.CTkProgressBar(self, height=14, progress_color=THEME["accent"])
        self.progress.pack(fill="x", padx=18, pady=(10, 2))
        self.progress.set(0)

        prog_info = ctk.CTkFrame(self, fg_color="transparent")
        prog_info.pack(fill="x", padx=18)
        self.status_label = ctk.CTkLabel(
            prog_info, text="Ready.", text_color=THEME["dim"],
            font=ctk.CTkFont(size=13), anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.count_label = ctk.CTkLabel(
            prog_info, text="", text_color=THEME["dim"],
            font=ctk.CTkFont(size=13),
        )
        self.count_label.pack(side="right")

        # Log --------------------------------------------------------------------
        self.log = ctk.CTkTextbox(
            self, height=150, fg_color=THEME["panel"],
            text_color=THEME["dim"], font=ctk.CTkFont(family="Consolas", size=12),
            border_width=1, border_color=THEME["border"],
        )
        self.log.pack(fill="both", expand=True, padx=18, pady=(8, 16))
        self.log.configure(state="disabled")

        self._select_profile(self.profile_key, persist=False)

    # --------------------------- profile logic ------------------------------

    def _select_profile(self, key: str, persist: bool = True) -> None:
        self.profile_key = key
        for k, btn in self.profile_buttons.items():
            if k == key:
                btn.configure(fg_color=THEME["accent"], border_color=THEME["accent"])
            else:
                btn.configure(fg_color=THEME["panel"], border_color=THEME["border"])

        if key == "custom":
            self.custom_frame.pack(fill="x", padx=18, pady=(2, 0), after=self.profile_desc)
            self.profile_desc.configure(text="Choose format and quality yourself.")
        else:
            self.custom_frame.pack_forget()
            prof = PROFILES[key]
            self.profile_desc.configure(text=prof.description)

        if persist:
            save_prefs(profile=key)

    def _sync_custom(self) -> None:
        self.custom_opts.update(
            format=self.fmt_var.get(),
            bitrate=self.br_var.get(),
            embed_metadata=self.meta_var.get(),
            embed_thumbnail=self.thumb_var.get(),
            sponsorblock=self.sb_var.get(),
        )

    def _current_profile(self) -> Profile:
        if self.profile_key == "custom":
            self._sync_custom()
            fmt = self.custom_opts["format"]
            lossless = fmt in ("flac", "wav")
            return custom_profile(
                format=fmt,
                bitrate=self.custom_opts["bitrate"],
                embed_metadata=self.custom_opts["embed_metadata"] and not lossless,
                embed_thumbnail=self.custom_opts["embed_thumbnail"] and not lossless,
                sponsorblock=self.custom_opts["sponsorblock"],
            )
        return get_profile(self.profile_key)

    def _pick_dest(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(initialdir=self.dest_var.get() or str(Path.home()))
        if chosen:
            self.dest_var.set(chosen)

    # --------------------------- download flow ------------------------------

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_download(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        url = self.url_entry.get().strip()
        if not url:
            self.status_label.configure(
                text="Paste a playlist URL first.", text_color=THEME["warn"]
            )
            self.url_entry.focus_set()
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            self.status_label.configure(
                text="That doesn't look like a URL.", text_color=THEME["warn"]
            )
            return

        dest = Path(self.dest_var.get().strip() or str(default_dest()))
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.status_label.configure(
                text=f"Cannot create folder: {exc}", text_color=THEME["err"]
            )
            return

        profile = self._current_profile()
        save_prefs(dest=str(dest), profile=self.profile_key, **{
            k: v for k, v in self.custom_opts.items()
            if k in ("format", "bitrate", "embed_metadata", "embed_thumbnail", "sponsorblock")
        })

        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress.set(0)
        self.count_label.configure(text="")
        self.status_label.configure(text="Starting...", text_color=THEME["dim"])
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        from ..deps import DependencyError, ensure_all, self_update_yt_dlp
        from ..engine import CancelToken, Engine

        self.cancel_token = CancelToken()

        def worker() -> None:
            try:
                self.queue.put(("log", "Checking dependencies..."))
                info = ensure_all(label=lambda m: self.queue.put(("log", f"  {m}")))
                self.queue.put(("log", f"  yt-dlp {info['yt_dlp']}, ffmpeg OK"))
                self_update_yt_dlp(label=lambda m: self.queue.put(("log", f"  {m}")))

                hooks = _QueueHooks(self.queue)
                engine = Engine(
                    profile,
                    ffmpeg_path=info["ffmpeg"],
                    hooks=hooks,
                    cancel=self.cancel_token,
                )
                report = engine.run(url, dest)
                self.queue.put(("done", report))
            except DependencyError as exc:
                self.queue.put(("error", str(exc)))
            except (KeyboardInterrupt, InterruptedError):
                self.queue.put(("cancelled", None))
            except Exception:
                self.queue.put(("error", traceback.format_exc(limit=3)))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def cancel_download(self) -> None:
        if self.cancel_token:
            self.cancel_token.cancel()
            self.status_label.configure(text="Cancelling...", text_color=THEME["warn"])
            self.cancel_btn.configure(state="disabled")

    # --------------------------- queue polling ------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    p = payload
                    self.progress.set(p.overall_percent / 100.0)
                    phase = {
                        "fetching": "Reading playlist...",
                        "downloading": f"Downloading: {p.title}",
                        "postprocessing": f"Processing: {p.title}",
                    }.get(p.phase, p.title)
                    self.status_label.configure(
                        text=phase[:90], text_color=THEME["dim"]
                    )
                    if p.total:
                        self.count_label.configure(
                            text=f"{p.index}/{p.total}"
                            + (f"  (+{p.skipped} kept)" if p.skipped else "")
                        )
                elif kind == "error":
                    self._finish_error(str(payload))
                elif kind == "cancelled":
                    self._finish_cancelled()
                elif kind == "done":
                    self._finish_report(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ------------------------------ results ---------------------------------

    def _reset_buttons(self) -> None:
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _finish_error(self, msg: str) -> None:
        self._reset_buttons()
        self.status_label.configure(text="Error (see log).", text_color=THEME["err"])
        self._log("--- ERROR ---")
        for line in msg.splitlines():
            self._log(line)

    def _finish_cancelled(self) -> None:
        self._reset_buttons()
        self.status_label.configure(text="Cancelled.", text_color=THEME["warn"])

    def _finish_report(self, report) -> None:
        self._reset_buttons()
        self.progress.set(1.0 if report.success else self.progress.get())
        n_ok, n_skip, n_fail = len(report.ok), len(report.skipped), len(report.failed)

        if report.cancelled:
            self.status_label.configure(
                text=f"Cancelled - {n_ok} downloaded.", text_color=THEME["warn"]
            )
        elif n_fail:
            self.status_label.configure(
                text=f"Finished with errors - {n_fail} failed.", text_color=THEME["warn"]
            )
            self._log("--- Failed songs ---")
            for title, err in report.failed:
                self._log(f"  {title}\n    {err[:160]}")
        else:
            self.status_label.configure(
                text=f"Done - {n_ok} downloaded"
                + (f", {n_skip} already had." if n_skip else "."),
                text_color=THEME["ok"],
            )

        self.count_label.configure(text=f"{n_ok}/{report.total}")
        if report.out_dir:
            self._log(f"Saved to: {report.out_dir}")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive() and self.cancel_token:
            from tkinter import messagebox

            if not messagebox.askyesno(
                "Download in progress",
                "A download is running. Cancel it and exit?",
            ):
                return
            self.cancel_token.cancel()
        save_prefs(geometry=self.geometry())
        self.destroy()


class _QueueHooks:
    """Engine hooks that push events into the GUI queue."""

    def __init__(self, q: queue.Queue) -> None:
        self.q = q

    def on_progress(self, progress) -> None:
        self.q.put(("progress", progress))

    def on_log(self, message: str) -> None:
        self.q.put(("log", message))


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
