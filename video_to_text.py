"""
Video ovozini matnga aylantirish dasturi (Speech-to-Text)
Tillar: O'zbek, Rus, Ingliz, Koreys, Xitoy (yoki avtomatik aniqlash)
Maksimal video hajmi: 1 GB

O'rnatish:
    pip install faster-whisper

Ishga tushirish:
    python video_to_text.py
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

MAX_SIZE_BYTES = 1 * 1024 ** 3  # 1 GB

LANGUAGES = {
    "O'zbek": "uz",
    "Русский (Rus)": "ru",
    "English (Ingliz)": "en",
    "한국어 (Koreys)": "ko",
    "中文 (Xitoy)": "zh",
    "Avtomatik aniqlash": None,
}

MODELS = ["tiny", "base", "small", "medium", "large-v3"]

VIDEO_TYPES = [
    ("Video fayllar", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.mp3 *.wav *.m4a"),
    ("Barcha fayllar", "*.*"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video → Matn")
        self.geometry("760x600")
        self.minsize(640, 500)

        self.video_path = tk.StringVar()
        self.lang_var = tk.StringVar(value="O'zbek")
        self.model_var = tk.StringVar(value="medium")
        self.timestamps_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Tayyor.")
        self.model_cache = {}
        self.worker = None

        self._build_ui()

    # ---------- Interfeys ----------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Video fayl:").pack(side="left")
        ttk.Entry(top, textvariable=self.video_path).pack(
            side="left", fill="x", expand=True, padx=5
        )
        ttk.Button(top, text="Tanlash...", command=self.choose_file).pack(side="left")

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        ttk.Label(opts, text="Til:").pack(side="left")
        ttk.Combobox(
            opts, textvariable=self.lang_var, values=list(LANGUAGES),
            state="readonly", width=20,
        ).pack(side="left", padx=5)
        ttk.Label(opts, text="Model:").pack(side="left", padx=(15, 0))
        ttk.Combobox(
            opts, textvariable=self.model_var, values=MODELS,
            state="readonly", width=10,
        ).pack(side="left", padx=5)
        ttk.Checkbutton(
            opts, text="Vaqt belgilari bilan", variable=self.timestamps_var
        ).pack(side="left", padx=15)

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="Matnga aylantirish", command=self.start)
        self.start_btn.pack(side="left")
        self.save_btn = ttk.Button(btns, text="Saqlash (.txt)", command=self.save_text)
        self.save_btn.pack(side="left", padx=8)
        ttk.Button(btns, text="Nusxalash", command=self.copy_text).pack(side="left")

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill="x", **pad)

        self.text = scrolledtext.ScrolledText(self, wrap="word", font=("Arial", 11))
        self.text.pack(fill="both", expand=True, **pad)

        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x", **pad)

    # ---------- Tugmalar ----------
    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=VIDEO_TYPES)
        if not path:
            return
        size = os.path.getsize(path)
        if size > MAX_SIZE_BYTES:
            messagebox.showerror(
                "Fayl juda katta",
                f"Fayl hajmi {size / 1024 ** 3:.2f} GB.\n"
                "Ruxsat etilgan maksimal hajm: 1 GB.",
            )
            return
        self.video_path.set(path)
        self.status_var.set(f"Tanlandi: {os.path.basename(path)} ({size / 1024 ** 2:.1f} MB)")

    def start(self):
        path = self.video_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Diqqat", "Avval video faylni tanlang.")
            return
        if os.path.getsize(path) > MAX_SIZE_BYTES:
            messagebox.showerror("Xato", "Fayl hajmi 1 GB dan oshmasligi kerak.")
            return

        self.start_btn.config(state="disabled")
        self.text.delete("1.0", "end")
        self.progress["value"] = 0
        self.worker = threading.Thread(target=self.transcribe, args=(path,), daemon=True)
        self.worker.start()

    def save_text(self):
        content = self.text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Bo'sh", "Saqlash uchun matn yo'q.")
            return
        default = os.path.splitext(os.path.basename(self.video_path.get() or "natija"))[0]
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=default + ".txt",
            filetypes=[("Matn fayli", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_var.set(f"Saqlandi: {path}")

    def copy_text(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end").strip())
        self.status_var.set("Matn nusxalandi.")

    # ---------- Asosiy ish ----------
    def get_model(self, name):
        if name in self.model_cache:
            return self.model_cache[name]
        from faster_whisper import WhisperModel

        self.set_status(f"'{name}' modeli yuklanmoqda (birinchi marta internetdan yuklab olinadi)...")
        try:
            model = WhisperModel(name, device="auto", compute_type="auto")
        except Exception:
            model = WhisperModel(name, device="cpu", compute_type="int8")
        self.model_cache[name] = model
        return model

    def transcribe(self, path):
        try:
            model = self.get_model(self.model_var.get())
            language = LANGUAGES[self.lang_var.get()]

            self.set_status("Ovoz matnga aylantirilmoqda...")
            segments, info = model.transcribe(
                path,
                language=language,
                vad_filter=True,   # sukunat qismlarini o'tkazib yuboradi
                beam_size=5,
            )

            total = info.duration or 1
            use_ts = self.timestamps_var.get()

            for seg in segments:
                line = seg.text.strip()
                if use_ts:
                    line = f"[{fmt_time(seg.start)} → {fmt_time(seg.end)}] {line}"
                self.append_text(line + "\n")
                self.set_progress(min(seg.end / total * 100, 100))

            self.set_progress(100)
            self.set_status(
                f"Tayyor! Aniqlangan til: {info.language} "
                f"(ishonchlilik: {info.language_probability:.0%})"
            )
        except ImportError:
            self.show_error("faster-whisper o'rnatilmagan.\n\nBuyruq: pip install faster-whisper")
        except Exception as e:
            self.show_error(f"Xatolik yuz berdi:\n{e}")
        finally:
            self.after(0, lambda: self.start_btn.config(state="normal"))

    # ---------- Thread-xavfsiz yordamchilar ----------
    def append_text(self, s):
        def _do():
            self.text.insert("end", s)
            self.text.see("end")
        self.after(0, _do)

    def set_status(self, s):
        self.after(0, lambda: self.status_var.set(s))

    def set_progress(self, v):
        self.after(0, lambda: self.progress.config(value=v))

    def show_error(self, msg):
        self.set_status("Xatolik.")
        self.after(0, lambda: messagebox.showerror("Xato", msg))


def fmt_time(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


if __name__ == "__main__":
    App().mainloop()
