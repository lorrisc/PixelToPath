"""Aperçu SVG — zoom molette ancré au curseur, pan glissé, comparaison.

Stratégie « cache + raffinement » :
- un rendu vectoriel complet est mis en cache (largeur naturelle, plafonné
  à _MAX_RENDER) ;
- pendant le geste (molette/pan), on découpe ce cache et on le redimensionne
  en BILINEAR — debounce 40 ms, dans une thread, garde `_gen` ;
- ~300 ms après le dernier geste, si le zoom exige plus de pixels que le
  cache, le SVG est re-rendu par cairosvg à la résolution affichée puis
  l'image est recomposée en LANCZOS.

La transparence est montrée par un damier PIL (tokens checker_a/checker_b,
rebâti au changement de thème/redimensionnement). La comparaison superpose
original et vectoriel à la même transformation mathématique (même région
naturelle, même zoom) : l'alignement est donc exact à tout zoom, la poignée
orange se glisse à la souris.
"""

import threading
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageTk

from core.i18n import t
from interface.theme.tokens import ThemeService

_MAX_RENDER = 4096   # plafond de rendu vectoriel (mémoire)
_ZOOM_MIN = 0.1
_ZOOM_MAX = 8.0
_ZOOM_STEP = 1.1
_DEBOUNCE_MS = 40
_REFINE_MS = 300
_MARGIN = 24         # marge du mode « ajuster »
_PAN_MARGIN = 40     # bornage du pan


def _rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class PreviewCanvas(tk.Canvas):
    """Canvas brut (pas CTk) : couleurs pilotées par apply_theme(tokens)."""

    def __init__(self, master, empty_text: str | None = None, **kw):
        super().__init__(master, bd=0, highlightthickness=0,
                         bg=ThemeService.color("canvas"), **kw)
        # Défaut résolu à la construction (jamais en défaut d'argument :
        # il serait figé à l'import, avant toute installation de langue).
        self._empty_text = (empty_text if empty_text is not None
                            else t("convert.preview_empty"))
        self._svg_path = None
        self._natural = (0, 0)
        self._original: Image.Image | None = None
        self._compare = False
        self._split = 0.5
        self._zoom = 1.0
        self._offset = (0.0, 0.0)
        self._box = (0, 0)
        self._cache: Image.Image | None = None   # rendu vectoriel complet
        self._cache_w = 0
        self._pending_fit = True
        self._checker: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None  # référence gardée
        self._drag = None  # None | ("pan", x, y) | ("split",)
        self._gen = 0
        self._job = None
        self._refine_job = None

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, _ZOOM_STEP))
        self.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / _ZOOM_STEP))
        self.bind("<MouseWheel>",
                  lambda e: self._zoom_at(e.x, e.y,
                                          _ZOOM_STEP if e.delta > 0 else 1 / _ZOOM_STEP))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ── API ───────────────────────────────────────────────────────────────
    def set_svg(self, svg_path: str, natural_size: tuple,
                original: Image.Image | None = None) -> None:
        """Nouveau résultat SVG (et image source pour la comparaison)."""
        self._svg_path = svg_path
        self._natural = natural_size
        self._original = original
        self._cache = None
        self._cache_w = 0
        if self._box == (0, 0):
            self._pending_fit = True  # ajusté au premier Configure
        else:
            self.fit()

    def clear(self) -> None:
        """État vide : message d'invitation sur fond canvas."""
        self._cancel_jobs()
        self._svg_path = None
        self._cache = None
        self._cache_w = 0
        self._original = None
        self._compare = False
        self._gen += 1
        self._redraw_empty()

    def fit(self) -> None:
        nat_w, nat_h = self._natural
        bw, bh = self._box
        if not nat_w or not bw:
            return
        self._zoom = max(_ZOOM_MIN, min(
            _ZOOM_MAX, min((bw - _MARGIN) / nat_w, (bh - _MARGIN) / nat_h)))
        self._offset = ((bw - nat_w * self._zoom) / 2,
                        (bh - nat_h * self._zoom) / 2)
        self._schedule()

    def zoom_1_1(self) -> None:
        if not self._natural[0]:
            return
        bw, bh = self._box
        # centrer sur le point actuellement visible
        cx = (bw / 2 - self._offset[0]) / self._zoom
        cy = (bh / 2 - self._offset[1]) / self._zoom
        self._zoom = 1.0
        self._offset = (bw / 2 - cx, bh / 2 - cy)
        self._clamp_offset()
        self._schedule()

    @property
    def compare(self) -> bool:
        return self._compare

    def set_compare(self, enabled: bool) -> None:
        if enabled and self._original is None:
            return
        self._compare = enabled
        self._schedule()

    def apply_theme(self, tokens: dict) -> None:
        self.configure(bg=tokens["canvas"])
        self._checker = None  # rebâti au prochain rendu
        if self._svg_path is None:
            self._redraw_empty()
        else:
            self._schedule()

    # ── Zoom / pan ────────────────────────────────────────────────────────
    def _zoom_at(self, wx: float, wy: float, factor: float) -> None:
        if not self._natural[0]:
            return
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        # le point d'image sous le curseur reste sous le curseur
        ix = (wx - self._offset[0]) / self._zoom
        iy = (wy - self._offset[1]) / self._zoom
        self._zoom = new_zoom
        self._offset = (wx - ix * new_zoom, wy - iy * new_zoom)
        self._clamp_offset()
        self._schedule()

    def _on_press(self, event):
        if self._compare and abs(event.x - self._split * self._box[0]) <= 12:
            self._drag = ("split",)
            self.configure(cursor="sb_h_double_arrow")
        else:
            self._drag = ("pan", event.x, event.y)
            self.configure(cursor="fleur")

    def _on_motion(self, event):
        if self._drag is None:
            return
        if self._drag[0] == "split":
            self._split = min(0.95, max(0.05, event.x / max(self._box[0], 1)))
        else:
            _, px, py = self._drag
            self._offset = (self._offset[0] + event.x - px,
                            self._offset[1] + event.y - py)
            self._drag = ("pan", event.x, event.y)
            self._clamp_offset()
        self._schedule()

    def _on_release(self, _event):
        was_drag = self._drag is not None
        self._drag = None
        self.configure(cursor="")
        if was_drag:
            self._schedule_refine()

    def _clamp_offset(self) -> None:
        bw, bh = self._box
        dw = self._natural[0] * self._zoom
        dh = self._natural[1] * self._zoom
        ox, oy = self._offset
        ox = ((bw - dw) / 2 if dw <= bw
              else min(_PAN_MARGIN, max(bw - dw - _PAN_MARGIN, ox)))
        oy = ((bh - dh) / 2 if dh <= bh
              else min(_PAN_MARGIN, max(bh - dh - _PAN_MARGIN, oy)))
        self._offset = (ox, oy)

    # ── Événements ────────────────────────────────────────────────────────
    def _on_resize(self, _event):
        w, h = self.winfo_width(), self.winfo_height()
        if (w, h) == self._box or w < 10:
            return
        self._box = (w, h)
        self._checker = None
        if self._svg_path is None:
            self._redraw_empty()
            return
        if self._pending_fit:
            self._pending_fit = False
            self.fit()
        else:
            self._clamp_offset()
            self._schedule()

    # ── Rendu ─────────────────────────────────────────────────────────────
    def _cancel_jobs(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if self._refine_job is not None:
            self.after_cancel(self._refine_job)
            self._refine_job = None

    def _schedule(self):
        if self._svg_path is None:
            self._redraw_empty()
            return
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(_DEBOUNCE_MS, self._render_async)

    def _schedule_refine(self):
        if self._refine_job is not None:
            self.after_cancel(self._refine_job)
        self._refine_job = self.after(_REFINE_MS, self._refine)

    def _refine(self):
        """Re-rendu vectoriel à la résolution affichée (fin de geste)."""
        self._refine_job = None
        if self._svg_path is None:
            return
        wanted = int(min(_MAX_RENDER, self._natural[0] * self._zoom))
        if wanted > self._cache_w:
            self._render_async(refine_width=wanted)

    def _render_async(self, refine_width: int | None = None):
        self._job = None
        if self._svg_path is None or self._box == (0, 0):
            return
        self._gen += 1
        gen = self._gen
        snapshot = dict(
            zoom=self._zoom, offset=self._offset, box=self._box,
            split=self._split,
            # l'image originale elle-même (None si comparaison inactive)
            compare=self._original if self._compare else None,
            refine_width=refine_width,
            quality="high" if refine_width else "normal",
            cache=self._cache,
        )
        svg_path = self._svg_path
        natural = self._natural
        checker = self._ensure_checker()

        def work():
            composed, rendered = self._compose(snapshot, svg_path, natural,
                                               checker)
            self.after(0, lambda: self._blit(gen, composed, rendered))

        threading.Thread(target=work, daemon=True, name="ptp-preview").start()

    def _ensure_checker(self) -> Image.Image:
        if self._checker is None or self._checker.size != self._box:
            self._checker = self._build_checker(*self._box)
        return self._checker

    def _compose(self, s: dict, svg_path, natural, checker):
        """Thread : rendu vectoriel au besoin + composition de la vue.

        Renvoie (PIL|None, rendu) — rendu = nouveau cache à retenir.
        """
        from core.convert_service import render_svg_to_pil

        cache = s["cache"]
        cache_w = cache.width if cache else 0
        try:
            if s["refine_width"] and s["refine_width"] > cache_w:
                cache = render_svg_to_pil(svg_path,
                                          output_width=s["refine_width"])
                cache_w = cache.width
            elif cache is None:
                cache = render_svg_to_pil(svg_path)
                cache_w = cache.width
        except Exception:
            return None, self._cache
        return self._compose_from(s, cache, natural, checker), cache

    def _compose_from(self, s: dict, cache: Image.Image, natural, checker):
        bw, bh = s["box"]
        canvas_img = checker.copy().convert("RGBA")
        # SVG d'abord sur toute la vue, puis l'original par-dessus la moitié
        # gauche : simple et sans couture (les deux couvrent le damier).
        self._paste_region(canvas_img, cache, cache.width / natural[0],
                           natural, s, quality=s["quality"])
        if s["compare"]:
            self._paste_region(canvas_img, s["compare"], 1.0, natural, s,
                               quality=s["quality"],
                               x_limit=int(s["split"] * bw))
        return canvas_img

    def _paste_region(self, target: Image.Image, source: Image.Image,
                      cs: float, natural, s: dict, quality: str = "normal",
                      x_limit: int | None = None) -> None:
        """Découpe la région visible dans `source` (cs px par px naturel),
        la redimensionne au zoom et la pose sur la vue. `x_limit` borne la
        pose à la partie gauche (moitié originale de la comparaison)."""
        zoom = s["zoom"]
        ox, oy = s["offset"]
        bw, bh = s["box"]
        x0 = max(0.0, -ox / zoom)
        y0 = max(0.0, -oy / zoom)
        x1 = min(natural[0], (bw - ox) / zoom)
        y1 = min(natural[1], (bh - oy) / zoom)
        if x1 <= x0 or y1 <= y0:
            return
        crop = source.crop((int(x0 * cs), int(y0 * cs),
                            min(source.width, int(x1 * cs) + 1),
                            min(source.height, int(y1 * cs) + 1)))
        dw = max(1, round((x1 - x0) * zoom))
        dh = max(1, round((y1 - y0) * zoom))
        piece = crop.resize((dw, dh), self._resample(quality)).convert("RGBA")
        px = int(round(ox + x0 * zoom))
        py = int(round(oy + y0 * zoom))
        if x_limit is not None:
            keep = max(0, min(piece.width, x_limit - px))
            if keep <= 0:
                return
            piece = piece.crop((0, 0, keep, piece.height))
        target.alpha_composite(piece, (max(0, px), max(0, py)))

    @staticmethod
    def _resample(quality: str):
        # BILINEAR pendant le geste (fluide), LANCZOS au repos (net).
        if quality == "high":
            return Image.Resampling.LANCZOS
        return Image.Resampling.BILINEAR

    def _blit(self, gen: int, composed, rendered):
        if gen != self._gen or composed is None:
            return
        if rendered is not None:
            self._cache = rendered
            self._cache_w = rendered.width
        self._photo = ImageTk.PhotoImage(composed)
        self.delete("all")
        self.create_image(0, 0, image=self._photo, anchor="nw")
        self._draw_overlays()
        self._schedule_refine()

    # ── Habillage (items canvas par-dessus l'image) ───────────────────────
    def _draw_overlays(self):
        tokens = ThemeService.tokens()
        bw, bh = self._box
        if self._compare:
            sx = int(self._split * bw)
            self.create_line(sx, 0, sx, bh, fill=tokens["primary"], width=2)
            self.create_rectangle(sx - 7, bh // 2 - 24, sx + 7, bh // 2 + 24,
                                  fill=tokens["primary"], outline="")
            self._label(t("convert.compare_original"), 12, 12, tokens,
                        anchor="w")
            self._label(t("convert.compare_vector"), bw - 12, 12, tokens,
                        anchor="e")
        else:
            self._label(f"{round(self._zoom * 100)} %", 12, bh - 12, tokens,
                        anchor="sw")

    def _label(self, text, x, y, tokens, anchor):
        # Pastille de fond : l'étiquette doit rester lisible sur n'importe
        # quel contenu (le gris « muted » se perd sur l'image convertie).
        w = tkfont.Font(font=("TkDefaultFont", 9, "bold")).measure(text)
        h = 14  # hauteur approximative du texte 9 pt gras
        pad_x, pad_y = 8, 4
        if anchor == "e":   # collée au bord droit : s'étend vers la gauche
            x0, x1 = x - w - 2 * pad_x, x
        else:               # "w" et "sw" : s'étend vers la droite
            x0, x1 = x, x + w + 2 * pad_x
        if anchor == "sw":  # ancrée par le bas (badge de zoom)
            y0, y1, cy = y - h - pad_y, y + pad_y, y - h / 2
        else:               # ancrée par le haut (comparaison)
            y0, y1, cy = y - pad_y, y + h + pad_y, y + h / 2
        self.create_rectangle(x0, y0, x1, y1, fill=tokens["surface"],
                              outline=tokens["border"])
        self.create_text((x0 + x1) / 2, cy, text=text, fill=tokens["text"],
                         font=("TkDefaultFont", 9, "bold"))

    def _redraw_empty(self):
        self.delete("all")
        tokens = ThemeService.tokens()
        bw, bh = self._box
        x = bw // 2 if bw else 300
        y = bh // 2 if bh else 200
        self.create_text(x, y, text=self._empty_text,
                         fill=tokens["faint"], font=("TkDefaultFont", 11))

    def _build_checker(self, w: int, h: int) -> Image.Image:
        tokens = ThemeService.tokens()
        a, b = _rgb(tokens["checker_a"]), _rgb(tokens["checker_b"])
        tile = Image.new("RGB", (40, 40), a)
        for cy in (0, 20):
            for cx in (0, 20):
                if (cx // 20 + cy // 20) % 2 == 0:
                    tile.paste(b, (cx, cy, cx + 20, cy + 20))
        img = Image.new("RGB", (max(w, 1), max(h, 1)), a)
        for y in range(0, h, 40):
            for x in range(0, w, 40):
                img.paste(tile, (x, y))
        return img
