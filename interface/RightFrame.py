import customtkinter as ctk
from PIL import Image, ImageOps
from tkinter import filedialog
from tkinterdnd2 import DND_FILES

import uuid, os, shutil, threading, sys

from moteur.image_utils import convert_to_svg, PRESETS
from interface.utils import resource_path

if sys.platform == "win32":
    gtk_bin_path = resource_path("bin/gtk-bin")
    os.environ["PATH"] = gtk_bin_path + os.pathsep + os.environ.get("PATH", "")

import cairosvg

# ── Palette ───────────────────────────────────────────────────────────────────
_BG = "#ebebeb"
_CARD = "#f5f5f5"
_BORDER = "#d8d8d8"
_MUTED = "#999999"
_GREEN = "#22aa55"
_AMBER = "#e09a00"
_RED = "#cc3333"
_CARD_H = 360 # hauteur dropzone
_SPINNER = ["◐", "◓", "◑", "◒"]

class _Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(
            parent, fg_color=_CARD,
            corner_radius=12, border_width=1, border_color=_BORDER, **kw,
        )

class RightFrame(ctk.CTkFrame):

    def __init__(self, parent, app_temp_dir: str, on_focus_toggle=None):
        super().__init__(parent)
        self.app_temp_dir = app_temp_dir
        self._on_focus_toggle = on_focus_toggle
        self._focus_mode = False

        self.loaded_image_path: str | None = None
        self.temp_svg_path: str | None = None
        self._orig_pil: Image.Image | None = None
        self._svg_pil:  Image.Image | None = None

        self._preview_id = None
        self._resize_id = None
        self._gen = 0
        self._is_busy = False
        self._spinner_id = None
        self._spinner_i = 0
        self._advanced_open = False
        self._sliders: dict = {}

        # ── Canvas scrollable ─────────────────────────────────────────────
        self._canvas = ctk.CTkCanvas(self, bd=0, highlightthickness=0, bg=_BG)
        self._vbar   = ctk.CTkScrollbar(
            self, orientation="vertical", command=self._canvas.yview
        )
        self.sf = ctk.CTkFrame(self._canvas, fg_color=_BG)

        self.sf.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )
        self._win = self._canvas.create_window((0, 0), window=self.sf, anchor="nw")
        self._canvas.configure(yscrollcommand=self._vbar.set)
        self._canvas.bind(
            "<Configure>",
            lambda e: (
                self._canvas.itemconfig(self._win, width=e.width),
                self._canvas.itemconfig(self._win, height=e.height),
            ),
        )
        self._canvas.pack(side="left", fill="both", expand=True)
        self._vbar.pack(side="right", fill="y")
        self._canvas.bind(
            "<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel),
        )
        self._canvas.bind(
            "<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"),
        )

        self._build()

    def _on_mousewheel(self, event):
        first, last = self._canvas.yview()
        if event.delta > 0 and first <= 0:
            return
        if event.delta < 0 and last >= 1:
            return
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build(self):
        # Statusbar en bas en premier (avant expand) pour ne pas être écrasée
        self._build_statusbar(self.sf)

        # Grille principale 2 colonnes — remplit toute la hauteur disponible
        self._main = ctk.CTkFrame(self.sf, fg_color=_BG)
        self._main.pack(fill="both", expand=True, padx=12, pady=(4, 0))
        self._main.columnconfigure(0, weight=2, minsize=200)
        self._main.columnconfigure(1, weight=3, minsize=280)
        self._main.rowconfigure(0, weight=1)

        # Colonne gauche : dropzone (hauteur fixe) + contrôles (s'étire)
        self._left_col = ctk.CTkFrame(self._main, fg_color=_BG)
        self._left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
        self._left_col.rowconfigure(1, weight=1)
        self._left_col.columnconfigure(0, weight=1)
        self._build_drop_card(self._left_col)
        self._build_controls_card(self._left_col)

        # Colonne droite : SVG pleine hauteur
        self._build_svg_card(self._main)

    def _build_drop_card(self, parent):
        self._drop_card = _Card(parent, height=_CARD_H)
        card = self._drop_card
        card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        card.grid_propagate(False)
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            hdr, text="ORIGINAL",
            font=ctk.CTkFont(size=9, weight="bold"), text_color=_MUTED,
        ).pack(side="left")

        self.lbl_orig = ctk.CTkLabel(
            card, text="Drag an image here\nor click to choose",
            justify="center", text_color=_MUTED,
        )
        self.lbl_orig.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        self.lbl_orig.bind("<Configure>", self._on_resize)

        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.lbl_filename = ctk.CTkLabel(
            foot, text="PNG · JPG · BMP · WebP",
            font=ctk.CTkFont(size=10), text_color=_MUTED,
        )
        self.lbl_filename.pack()

        for w in (card, self.lbl_orig):
            w.bind("<Button-1>", self.load_image)
        card.drop_target_register(DND_FILES)
        card.dnd_bind("<<Drop>>", self.on_file_drop)

    def _build_controls_card(self, parent):
        self._controls_card = _Card(parent)
        card = self._controls_card
        card.grid(row=1, column=0, sticky="nsew")

        # Scrollable interne pour que le contenu ne déborde pas
        inner = ctk.CTkScrollableFrame(
            card, fg_color="transparent",
            scrollbar_button_color=_BORDER,
            scrollbar_button_hover_color=_MUTED,
        )
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Presets ───────────────────────────────────────────────────────
        self._section(inner, "Presets")
        pr = ctk.CTkFrame(inner, fg_color="transparent")
        pr.pack(fill="x", padx=16, pady=(4, 10))
        for lbl, key in [("B&W", "bw"), ("Poster", "poster"), ("Photo", "photo")]:
            ctk.CTkButton(
                pr, text=lbl, width=68, height=30,
                command=lambda k=key: self._apply_preset(k),
            ).pack(side="left", padx=(0, 6))

        # ── Bouton Advanced ───────────────────────────────────────────────
        adv_wrap = ctk.CTkFrame(inner, fg_color="transparent")
        adv_wrap.pack(fill="x", padx=16, pady=(6, 4))
        self._btn_adv = ctk.CTkButton(
            adv_wrap,
            text="⚙  Advanced  ▾",
            height=28, fg_color="transparent",
            border_width=1, border_color=_BORDER,
            text_color=_MUTED, hover_color=_BORDER,
            command=self._toggle_advanced,
        )
        self._btn_adv.pack(fill="x")

        # ── Frame Advanced (masqué par défaut) ────────────────────────────
        self._frame_adv = ctk.CTkFrame(inner, fg_color="transparent")

        # Color Mode (dans advanced)
        self._section(self._frame_adv, "Color Mode")
        self.seg_colormode = ctk.CTkSegmentedButton(
            self._frame_adv, values=["Color", "Binary"],
            command=self._on_param_change,
        )
        self.seg_colormode.set("Color")
        self.seg_colormode.pack(fill="x", padx=16, pady=(4, 8))

        # Invert switch (Binary uniquement, dans advanced)
        self._invert_row = ctk.CTkFrame(self._frame_adv, fg_color="transparent")
        ir_lbl = ctk.CTkFrame(self._invert_row, fg_color="transparent")
        ir_lbl.pack(fill="x", padx=16, pady=(2, 0))
        ir_lbl.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            ir_lbl, text="Invert",
            font=ctk.CTkFont(size=12), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            ir_lbl, text="Swap black ↔ white",
            font=ctk.CTkFont(size=10), text_color=_MUTED, anchor="e",
        ).grid(row=0, column=1, sticky="e")
        self.switch_invert = ctk.CTkSwitch(
            self._invert_row, text="",
            command=self._on_param_change, width=42, height=22,
        )
        self.switch_invert.pack(anchor="w", padx=16, pady=(2, 8))

        # Params couleur (dans advanced)
        self._frame_color = ctk.CTkFrame(self._frame_adv, fg_color="transparent")
        self._frame_color.pack(fill="x")
        self._make_slider(
            self._frame_color, "color_precision",
            "Color Precision", 1, 8, 6, 7, "{:.0f}")
        self._make_slider(
            self._frame_color, "layer_difference",
            "Layer Difference", 1, 64, 16, 63, "{:.0f}")
        self._section(self._frame_color, "Hierarchical")
        self.seg_hierarchical = ctk.CTkSegmentedButton(
            self._frame_color, values=["Stacked", "Cutout"],
            command=self._on_param_change,
        )
        self.seg_hierarchical.set("Stacked")
        self.seg_hierarchical.pack(fill="x", padx=16, pady=(4, 8))

        # Curve Fitting
        self._section(self._frame_adv, "Curve Fitting")
        self.seg_mode = ctk.CTkSegmentedButton(
            self._frame_adv, values=["Spline", "Polygon", "Pixel"],
            command=self._on_param_change,
        )
        self.seg_mode.set("Spline")
        self.seg_mode.pack(fill="x", padx=16, pady=(4, 8))

        self._make_slider(
            self._frame_adv, "filter_speckle",
            "Filter Speckle", 0, 16, 4, 16, "{:.0f}")
        self._make_slider(
            self._frame_adv, "corner_threshold",
            "Corner Threshold", 0, 180, 60, 180, "{:.0f}")
        self._make_slider(
            self._frame_adv, "length_threshold",
            "Length Threshold", 3.5, 10.0, 4.0, 65, "{:.1f}")

        self._section(self._frame_adv, "Fine-tuning")
        self._make_slider(
            self._frame_adv, "splice_threshold",
            "Splice Threshold", 0, 180, 45, 180, "{:.0f}")
        self._make_slider(
            self._frame_adv, "max_iterations",
            "Max Iterations", 1, 20, 10, 19, "{:.0f}")

        ctk.CTkFrame(inner, fg_color="transparent", height=8).pack()

    # ── Carte SVG (col droite, pleine hauteur) ────────────────────────────

    def _build_svg_card(self, parent):
        self._svg_card = _Card(parent)
        self._svg_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)
        card = self._svg_card
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)

        # En-tête
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            hdr, text="SVG PREVIEW",
            font=ctk.CTkFont(size=9, weight="bold"), text_color=_MUTED,
        ).pack(side="left")
        self.lbl_live = ctk.CTkLabel(
            hdr, text="● live",
            font=ctk.CTkFont(size=10), text_color=_GREEN,
        )
        self.lbl_live.pack(side="right")

        # Image SVG (s'étire)
        self.lbl_svg = ctk.CTkLabel(
            card, text="Waiting for image…",
            justify="center", text_color=_MUTED,
        )
        self.lbl_svg.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        self.lbl_svg.bind("<Configure>", self._on_resize)

        # Pied : info + download + statut save
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

        self.lbl_svg_info = ctk.CTkLabel(
            foot, text="",
            font=ctk.CTkFont(size=10), text_color=_MUTED,
        )
        self.lbl_svg_info.pack(pady=(0, 6))

        self.btn_download = ctk.CTkButton(
            foot, text="↓  Download SVG",
            height=36, width=180,
            command=self.download_svg, state="disabled",
        )
        self.btn_download.pack(pady=(0, 4))

        self.lbl_save_status = ctk.CTkLabel(
            foot, text="",
            font=ctk.CTkFont(size=10), text_color=_GREEN,
        )
        self.lbl_save_status.pack()

    # ── Barre de statut ───────────────────────────────────────────────────

    def _build_statusbar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=_BG)
        bar.pack(fill="x", padx=14, pady=(8, 6))

        self.lbl_status = ctk.CTkLabel(
            bar, text="", font=ctk.CTkFont(size=12), anchor="w",
        )
        self.lbl_status.pack(side="left", padx=2)

        self._btn_focus = ctk.CTkButton(
            bar,
            text="⛶  Focus",
            height=30, width=100,
            fg_color="transparent",
            border_width=1, border_color=_BORDER,
            text_color=_MUTED, hover_color=_BORDER,
            command=self._toggle_focus,
        )
        self._btn_focus.pack(side="right", padx=2)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers widgets
    # ══════════════════════════════════════════════════════════════════════

    def _section(self, parent, text: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=(10, 0))
        ctk.CTkLabel(
            f, text=text.upper(),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=_MUTED, anchor="w",
        ).pack(side="left")
        ctk.CTkFrame(f, height=1, fg_color=_BORDER).pack(
            side="right", fill="x", expand=True, padx=(6, 0), pady=5,
        )

    def _make_slider(self, parent, key, label, lo, hi, default, steps, fmt):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 0))
        row.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row, text=label, anchor="w", font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="w")
        val_lbl = ctk.CTkLabel(
            row, text=fmt.format(default),
            anchor="e", font=ctk.CTkFont(size=11), text_color=_MUTED,
        )
        val_lbl.grid(row=0, column=1, sticky="e")

        sl = ctk.CTkSlider(parent, from_=lo, to=hi, number_of_steps=steps)
        sl.set(default)
        sl.pack(fill="x", padx=16, pady=(2, 4))
        sl.configure(
            command=lambda v, l=val_lbl, f=fmt: (
                l.configure(text=f.format(v)),
                self._on_param_change(),
            )
        )
        self._sliders[key] = (sl, val_lbl, fmt)

    def _set_slider(self, key, value):
        s, lbl, fmt = self._sliders[key]
        s.set(value)
        lbl.configure(text=fmt.format(value))

    # ══════════════════════════════════════════════════════════════════════
    # Visibilité
    # ══════════════════════════════════════════════════════════════════════

    def _toggle_focus(self):
        self._focus_mode = not self._focus_mode
        if self._focus_mode:
            self._drop_card.grid_remove()
            self._btn_focus.configure(text="⛶  Exit Focus")
            self.winfo_toplevel().bind("<Escape>", lambda e: self._exit_focus())
        else:
            self._drop_card.grid()
            self._btn_focus.configure(text="⛶  Focus")
            self.winfo_toplevel().unbind("<Escape>")
        if self._on_focus_toggle:
            self._on_focus_toggle()

    def _exit_focus(self):
        """Appelé par Escape — sort du focus mode si actif."""
        if self._focus_mode:
            self._toggle_focus()

    def _on_colormode_vis(self, mode: str):
        """Affiche/masque Invert et les params couleur dans Advanced."""
        if mode == "Color":
            self._invert_row.pack_forget()
            self._frame_color.pack(fill="x")
        else:
            self._frame_color.pack_forget()
            self._invert_row.pack(fill="x", after=self.seg_colormode)

    def _toggle_advanced(self):
        self._advanced_open = not self._advanced_open
        if self._advanced_open:
            self._frame_adv.pack(fill="x", after=self._btn_adv.master)
            self._btn_adv.configure(text="⚙  Advanced  ▴")
            self._on_colormode_vis(self.seg_colormode.get())
        else:
            self._frame_adv.pack_forget()
            self._btn_adv.configure(text="⚙  Advanced  ▾")

    def _on_param_change(self, *_):
        self._on_colormode_vis(self.seg_colormode.get())
        self._schedule_preview()

    def _apply_preset(self, key: str):
        p = PRESETS[key]
        cm = p.get("colormode", "color")
        self.seg_colormode.set("Color" if cm == "color" else "Binary")
        self._on_colormode_vis(self.seg_colormode.get())

        if "color_precision"  in p: self._set_slider("color_precision",  p["color_precision"])
        if "layer_difference" in p: self._set_slider("layer_difference", p["layer_difference"])
        if "hierarchical"     in p: self.seg_hierarchical.set(p["hierarchical"].capitalize())

        mode_map = {"spline": "Spline", "polygon": "Polygon", "none": "Pixel"}
        self.seg_mode.set(mode_map.get(p.get("mode", "spline"), "Spline"))

        for k in ("filter_speckle", "corner_threshold", "length_threshold",
                  "splice_threshold", "max_iterations"):
            if k in p:
                self._set_slider(k, p[k])

        self._schedule_preview()

    # ══════════════════════════════════════════════════════════════════════
    # Chargement d'image
    # ══════════════════════════════════════════════════════════════════════

    _EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    def load_image_from_path(self, filepath: str):
        if not filepath:
            return
        self.loaded_image_path = filepath
        self._orig_pil = Image.open(filepath).convert("RGBA")
        self._show_pil(self.lbl_orig, self._orig_pil, "_ctk_orig")

        name = os.path.basename(filepath)
        w, h = self._orig_pil.size
        self.lbl_filename.configure(text=f"{name}  —  {w} × {h} px")

        self._svg_pil = None
        self.lbl_svg.configure(image=None, text="Converting…", text_color=_MUTED)
        self.lbl_svg_info.configure(text="")
        self.lbl_save_status.configure(text="")
        self.btn_download.configure(state="disabled")
        self._schedule_preview()

    def load_image(self, event=None):
        fp = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        self.load_image_from_path(fp)

    def on_file_drop(self, event):
        fp = event.data.strip("{}")
        if fp.lower().endswith(self._EXTS):
            self.load_image_from_path(fp)
        else:
            self._set_status_error("Format not accepted — use PNG, JPG, BMP or WebP")

    # ══════════════════════════════════════════════════════════════════════
    # Affichage CTkImage
    # ══════════════════════════════════════════════════════════════════════

    def _show_pil(self, label: ctk.CTkLabel, pil_img: Image.Image, ref: str):
        if pil_img is None:
            return
        lw = max(label.winfo_width()  - 28, 80)
        lh = max(label.winfo_height() - 28, 80)
        img = pil_img.copy()
        img.thumbnail((lw, lh), Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img, size=(img.width, img.height),
        )
        label.configure(image=ctk_img, text="")
        setattr(self, ref, ctk_img)

    def _on_resize(self, event=None):
        if self._resize_id:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(120, self._redisplay_images)

    def _redisplay_images(self):
        if self._orig_pil:
            self._show_pil(self.lbl_orig, self._orig_pil, "_ctk_orig")
        if self._svg_pil:
            self._show_pil(self.lbl_svg, self._svg_pil, "_ctk_svg")

    # ══════════════════════════════════════════════════════════════════════
    # Live preview
    # ══════════════════════════════════════════════════════════════════════

    def _schedule_preview(self):
        if not self.loaded_image_path:
            return
        if self._preview_id:
            self.after_cancel(self._preview_id)
        self._preview_id = self.after(600, self._run_conversion)

    def _prepare_input(self) -> str:
        tmp = os.path.join(self.app_temp_dir, f"input_{uuid.uuid4().hex}.png")
        img = self._orig_pil.convert("RGBA")
        if self.seg_colormode.get() == "Binary":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg.convert("L").convert("RGB")
            if self.switch_invert.get():
                img = ImageOps.invert(img)
        img.save(tmp, "PNG")
        return tmp

    def _collect_params(self) -> dict:
        colormode = self.seg_colormode.get().lower()
        mode_map  = {"Spline": "spline", "Polygon": "polygon", "Pixel": "none"}
        p = dict(
            colormode        = colormode,
            mode             = mode_map.get(self.seg_mode.get(), "spline"),
            filter_speckle   = int(self._sliders["filter_speckle"][0].get()),
            corner_threshold = int(self._sliders["corner_threshold"][0].get()),
            length_threshold = round(self._sliders["length_threshold"][0].get(), 2),
            splice_threshold = int(self._sliders["splice_threshold"][0].get()),
            max_iterations   = int(self._sliders["max_iterations"][0].get()),
            path_precision   = 3,
        )
        if colormode == "color":
            p["hierarchical"]     = self.seg_hierarchical.get().lower()
            p["color_precision"]  = int(self._sliders["color_precision"][0].get())
            p["layer_difference"] = int(self._sliders["layer_difference"][0].get())
        return p

    def _run_conversion(self):
        if not self.loaded_image_path or self._orig_pil is None:
            return
        self._gen += 1
        gen    = self._gen
        params = self._collect_params()
        out    = os.path.join(self.app_temp_dir, f"{uuid.uuid4().hex}.svg")
        self._start_spinner()

        def _task():
            tmp_in = None
            try:
                tmp_in = self._prepare_input()
                convert_to_svg(tmp_in, out, **params)
                self.after(0, lambda: self._on_done(gen, out))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(gen, str(e)))
            finally:
                if tmp_in and os.path.exists(tmp_in):
                    try:
                        os.remove(tmp_in)
                    except OSError:
                        pass

        threading.Thread(target=_task, daemon=True).start()

    def _on_done(self, gen: int, path: str):
        if gen != self._gen:
            return
        self._stop_spinner()
        self.temp_svg_path = path
        self._render_svg_preview()
        self._set_status_ok()
        self.btn_download.configure(state="normal")
        self.lbl_save_status.configure(text="")

    def _on_error(self, gen: int, msg: str):
        if gen != self._gen:
            return
        self._stop_spinner()
        self._set_status_error(msg)

    def _start_spinner(self):
        self._is_busy   = True
        self._spinner_i = 0
        self._tick()

    def _tick(self):
        if not self._is_busy:
            return
        c = _SPINNER[self._spinner_i % 4]
        self.lbl_status.configure(text=f"{c}  Converting…", text_color=_MUTED)
        self.lbl_live.configure(text="● converting", text_color=_AMBER)
        self._spinner_i += 1
        self._spinner_id = self.after(130, self._tick)

    def _stop_spinner(self):
        self._is_busy = False
        if self._spinner_id:
            self.after_cancel(self._spinner_id)
            self._spinner_id = None

    def _set_status_ok(self):
        self.lbl_status.configure(text="✓  Ready", text_color=_GREEN)
        self.lbl_live.configure(text="● live", text_color=_GREEN)

    def _set_status_error(self, msg: str):
        short = msg if len(msg) < 90 else msg[:87] + "…"
        self.lbl_status.configure(text=f"✕  {short}", text_color=_RED)
        self.lbl_live.configure(text="● error", text_color=_RED)

    # ══════════════════════════════════════════════════════════════════════
    # Rendu SVG
    # ══════════════════════════════════════════════════════════════════════

    def _render_svg_preview(self):
        if not self.temp_svg_path:
            return
        try:
            tmp = os.path.join(self.app_temp_dir, f"{uuid.uuid4().hex}.png")
            cairosvg.svg2png(url=self.temp_svg_path, write_to=tmp)
            self._svg_pil = Image.open(tmp).convert("RGBA")
            os.remove(tmp)
            self._show_pil(self.lbl_svg, self._svg_pil, "_ctk_svg")
            size_kb = os.path.getsize(self.temp_svg_path) / 1024
            self.lbl_svg_info.configure(text=f"{size_kb:.1f} KB  ·  SVG")
        except Exception as exc:
            self.lbl_svg.configure(
                image=None, text=f"Preview error:\n{exc}", text_color=_RED,
            )

    # ══════════════════════════════════════════════════════════════════════
    # Téléchargement
    # ══════════════════════════════════════════════════════════════════════

    def download_svg(self):
        if not self.temp_svg_path or not os.path.exists(self.temp_svg_path):
            self.lbl_save_status.configure(
                text="No SVG available.", text_color=_RED
            )
            return
        save_path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG", "*.svg")],
            title="Save SVG as…",
        )
        if save_path:
            shutil.copyfile(self.temp_svg_path, save_path)
            name = os.path.basename(save_path)
            self.lbl_save_status.configure(
                text=f"✓  Saved: {name}", text_color=_GREEN,
            )
            self.lbl_status.configure(
                text=f"✓  Saved: {name}", text_color=_GREEN,
            )