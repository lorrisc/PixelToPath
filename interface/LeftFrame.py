"""
LeftFrame.py
Panneau gauche : documentation PixelToPath.
Les détails de paramètres sont masqués par défaut derrière Advanced.
"""

import customtkinter as ctk
from PIL import Image
import webbrowser
from interface.utils import resource_path

_MUTED  = "#999999"
_BORDER = "#d8d8d8"


class LeftFrame(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent)
        self._adv_open = False

        self.canvas = ctk.CTkCanvas(
            self, borderwidth=0, highlightthickness=0, bg="#dbdbdb"
        )
        self.scrollbar = ctk.CTkScrollbar(
            self, orientation="vertical", command=self.canvas.yview
        )
        self.sf = ctk.CTkFrame(self.canvas)

        self.sf.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )
        self._win = self.canvas.create_window(
            (0, 0), window=self.sf, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._win, width=e.width),
        )
        self.canvas.bind(
            "<Enter>",
            lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel),
        )
        self.canvas.bind(
            "<Leave>",
            lambda e: self.canvas.unbind_all("<MouseWheel>"),
        )

        self._build()

    def _on_mousewheel(self, event):
        first, last = self.canvas.yview()
        if event.delta > 0 and first <= 0:
            return
        if event.delta < 0 and last >= 1:
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Construction ──────────────────────────────────────────────────────

    def _build(self):
        sf = self.sf

        # Titre
        ctk.CTkLabel(
            sf, text="About PixelToPath",
            font=ctk.CTkFont(size=18, weight="bold"), anchor="center",
        ).pack(pady=(14, 4), padx=12, fill="x")

        # Description
        self._title(sf, "Description")
        self._text(sf,
            "PixelToPath converts images (PNG, JPG, BMP, WebP) into SVG "
            "vector graphics using VTracer — an open-source Rust-based tracer "
            "that handles both color and black-and-white images natively."
        )

        # Presets
        self._title(sf, "Presets")
        for name, desc in [
            ("B&W",    "Binary tracing — fast and clean. Ideal for logos and line art."),
            ("Poster", "Color tracing with tight layers. Best for flat illustrations."),
            ("Photo",  "Color tracing optimised for photographs with softer gradients."),
        ]:
            self._param(sf, name, desc)

        # Bouton Advanced
        adv_wrap = ctk.CTkFrame(sf, fg_color="transparent")
        adv_wrap.pack(fill="x", padx=12, pady=(12, 4))
        self._btn_adv = ctk.CTkButton(
            adv_wrap,
            text="⚙  Advanced Parameters  ▾",
            height=28, fg_color="transparent",
            border_width=1, border_color=_BORDER,
            text_color=_MUTED, hover_color=_BORDER,
            command=self._toggle_advanced,
        )
        self._btn_adv.pack(fill="x")

        # Contenu Advanced (masqué)
        self._adv_frame = ctk.CTkFrame(sf, fg_color="transparent")
        # Ne pas packer ici.

        af = self._adv_frame

        self._title(af, "Color Mode")
        self._text(af,
            "Color traces the image across multiple color layers. "
            "Binary converts to grayscale first — use the Invert switch "
            "if your subject appears white on a white background."
        )

        self._atitle(af, "Color Precision")
        self._atext(af,
            "Number of significant bits per RGB channel (1–8). "
            "Higher = more distinct colors. Lower = broader color merging."
        )
        self._atitle(af, "Layer Difference")
        self._atext(af,
            "Minimum color gap between adjacent layers (1–64). "
            "Higher = fewer, broader color regions."
        )
        self._atitle(af, "Hierarchical")
        for name, desc in [
            ("Stacked",
             "Layers sit on top of each other. Compact output, no holes. Recommended."),
            ("Cutout",
             "Each layer is cut out from those below. Useful when shapes must not overlap."),
        ]:
            self._aparam(af, name, desc)

        self._atitle(af, "Curve Fitting")
        for name, desc in [
            ("Spline",   "Smooth Bézier curves. Best overall quality."),
            ("Polygon",  "Straight segments only. Good for geometric artwork."),
            ("Pixel",    "No smoothing — pixel-perfect. Ideal for pixel art."),
        ]:
            self._aparam(af, name, desc)

        self._atitle(af, "Other Parameters")
        for name, desc in [
            ("Filter Speckle",
             "Discards patches smaller than N px. Higher = less noise."),
            ("Corner Threshold",
             "Minimum angle (°) to detect a sharp corner. Lower = more corners."),
            ("Length Threshold",
             "Max segment length before subdivision (3.5–10). Lower = more detail."),
            ("Splice Threshold",
             "Minimum angle to break a spline. Affects curve continuity."),
            ("Max Iterations",
             "Smoothing passes. More = smoother result, but slower."),
        ]:
            self._aparam(af, name, desc)

        # Spacer + PayPal
        ctk.CTkLabel(sf, text="").pack()

        def _open_paypal():
            webbrowser.open(
                "https://www.paypal.com/donate/?hosted_button_id=6TCT576QMTBAL"
            )

        pp_img = ctk.CTkImage(
            light_image=Image.open(resource_path("interface/assets/paypal.png")),
            dark_image =Image.open(resource_path("interface/assets/paypal.png")),
            size=(200, 78.5),
        )
        ctk.CTkButton(
            sf, image=pp_img, text="", command=_open_paypal,
            width=200, height=78.5, fg_color="transparent", hover=False,
        ).pack(pady=20)

    # ── Toggle ────────────────────────────────────────────────────────────

    def _toggle_advanced(self):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(
                fill="x", after=self._btn_adv.master
            )
            self._btn_adv.configure(text="⚙  Advanced Parameters  ▴")
        else:
            self._adv_frame.pack_forget()
            self._btn_adv.configure(text="⚙  Advanced Parameters  ▾")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _title(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).pack(pady=(10, 2), padx=12, anchor="w")

    def _text(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            wraplength=295, justify="left", anchor="w",
        ).pack(pady=(0, 6), padx=12, anchor="w")

    def _param(self, parent, title: str, desc: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=12, pady=(3, 5))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            f, text=desc, wraplength=285, justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="w")

    def _atitle(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(pady=(8, 1), padx=12, anchor="w")

    def _atext(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text,
            wraplength=285, justify="left", anchor="w",
        ).pack(pady=(0, 4), padx=12, anchor="w")

    def _aparam(self, parent, title: str, desc: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=12, pady=(3, 4))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            f, text=desc, wraplength=285, justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="w")