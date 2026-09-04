"""Zone de dépôt — la signature visuelle de PixelToPath.

Pas d'illustration : un grand cadre en pointillés (la convention
universelle du dropzone) autour d'une invite typographique centrée. Le
cadre vit sur un canvas posé au-dessus du fond de la carte et sous les
enfants ; il passe à la couleur d'accent pendant un survol de
glisser-déposer. Tout est re-dessiné à chaque resize/changement de thème
(CTkCanvas ignore l'apparence ctk).

Le widget est muet : il émet on_activate() (clic), on_drop(chemins)
(glisser-déposer, chemins éclatés via splitlist) et on_remove() (bouton
Supprimer de l'état chargé).
"""

import customtkinter as ctk
from tkinterdnd2 import DND_FILES

from core.i18n import t
from interface.theme.tokens import ThemeService, pair
from interface.widgets.card import Card, GhostButton

_INSET = 6   # marge du cadre pointillé dans la carte
_RADIUS = 10  # rayon des coins du cadre pointillé


class _RemoveButton(GhostButton):
    """Action destructive : grammaire GhostButton, teinte error."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.configure(text_color=pair("error"))

    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self.configure(text_color=pair("error"))


_EMPTY: ctk.CTkImage | None = None


def _empty_image() -> ctk.CTkImage:
    """Vignette neutre 1×1, tenue vivante pendant tout le processus.

    Détacher l'image d'un CTkLabel avec None ne marche pas : ctk ignore
    alors la mise à jour du label interne, qui garde l'option de l'ancien
    PhotoImage — une fois le CTkImage collecté, le prochain configure
    lève TclError « image "pyimageN" does not exist ».
    """
    global _EMPTY
    if _EMPTY is None:
        from PIL import Image
        _EMPTY = ctk.CTkImage(light_image=Image.new("RGBA", (1, 1)))
    return _EMPTY


class Dropzone(Card):
    def __init__(self, master, on_activate, on_drop, on_remove=None, **kw):
        super().__init__(master, **kw)
        # La carte perd son liseré propre : le cadre pointillé EST la
        # frontière (des coins arrondis seraient recouverts par le canvas).
        # Configure() après coup : Card fige corner_radius avant **kw.
        self.configure(corner_radius=0, border_width=0)
        self._on_activate = on_activate
        self._on_drop = on_drop
        self._on_remove = on_remove
        self._image = None  # CTkImage de la vignette (référence gardée)
        self._drag_hover = False

        # ── Fond : cadre pointillé (placé en premier → sous les enfants) ──
        self._border = ctk.CTkCanvas(
            self, bd=0, highlightthickness=0,
            bg=ThemeService.color("surface"),
        )
        self._border.place(x=0, y=0, relwidth=1, relheight=1)
        self._border.bind("<Configure>", lambda _e: self._draw_border())
        self._border.bind("<Button-1>", lambda _e: self._on_activate())
        self._border.configure(cursor="hand2")

        # ── Contenu : une colonne pleine largeur (les labels, ancrés au
        # centre par défaut, se centrent donc dans la carte) + ressorts
        # haut/bas pour un recentrage vertical si la carte s'étire. ────────
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ── État vide : l'invite tient lieu d'image ────────────────────────
        self._title = ctk.CTkLabel(
            self, text=t("convert.drop_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=pair("heading"),
        )
        self._title.grid(row=1, column=0, pady=(24, 0))

        self._sub = ctk.CTkLabel(
            self, text=t("convert.drop_sub"),
            font=ctk.CTkFont(size=11), text_color=pair("muted"),
        )
        self._sub.grid(row=2, column=0, pady=(4, 0))

        self._formats = ctk.CTkLabel(
            self, text=t("convert.drop_formats"),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=pair("faint"),
        )
        self._formats.grid(row=3, column=0, pady=(10, 24))

        # ── État chargé (masqué) : vignette + méta + actions ───────────────
        self._thumb = ctk.CTkLabel(self, text="")
        self._thumb.grid(row=1, column=0, pady=(18, 0))
        self._meta = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=10),
            text_color=pair("muted"),
        )
        self._meta.grid(row=2, column=0, pady=(8, 0))
        self._actions = ctk.CTkFrame(self, fg_color="transparent")
        self._actions.grid(row=3, column=0, pady=(10, 20))
        self._btn_change = GhostButton(
            self._actions, text=t("convert.change_image"), width=130,
            height=30, command=lambda: self._on_activate(),
        )
        self._btn_change.grid(row=0, column=0, padx=(0, 8))
        self._btn_remove = _RemoveButton(
            self._actions, text=t("common.delete"), width=96, height=30,
            command=self._request_remove,
        )
        self._btn_remove.grid(row=0, column=1)
        self._show_loaded(False)

        for w in (self, self._border, self._title, self._sub, self._formats,
                  self._thumb, self._meta):
            w.bind("<Button-1>", lambda _e: self._on_activate())
            w.configure(cursor="hand2")

        # La vignette (enfant CTk interne) échappe au bind du label : la
        # cible de dépôt est posée sur la carte ET sur le canvas de fond.
        for target in (self, self._border):
            target.drop_target_register(DND_FILES)
            target.dnd_bind("<<Drop>>", self._on_file_drop)
            target.dnd_bind("<<DropEnter>>", lambda _e: self._set_drag(True))
            target.dnd_bind("<<DropLeave>>", lambda _e: self._set_drag(False))

    # ── États ─────────────────────────────────────────────────────────────
    def set_image(self, pil_image, meta_text: str) -> None:
        """Affiche la vignette de l'image chargée (état plein)."""
        img = pil_image.copy()
        img.thumbnail((280, 150), _resample())
        self._image = ctk.CTkImage(
            light_image=img, dark_image=img, size=(img.width, img.height)
        )
        self._thumb.configure(image=self._image, text="")
        self._meta.configure(text=meta_text)
        self._show_loaded(True)

    def reset(self) -> None:
        """Revient à l'état vide (invite de dépôt). Idempotent."""
        if self._image is not None:
            self._thumb.configure(image=_empty_image(), text="")
            self._image = None
        self._set_drag(False)
        self._show_loaded(False)

    def _show_loaded(self, loaded: bool) -> None:
        for w, show in (
            (self._title, not loaded), (self._sub, not loaded),
            (self._formats, not loaded),
            (self._thumb, loaded), (self._meta, loaded),
            (self._actions, loaded),
        ):
            w.grid() if show else w.grid_remove()

    def _request_remove(self) -> None:
        self.reset()
        if self._on_remove is not None:
            self._on_remove()

    # ── DnD ───────────────────────────────────────────────────────────────
    def _on_file_drop(self, event):
        self._set_drag(False)  # certains WM n'émettent pas DropLeave
        # splitlist (et non strip("{}")) : gère les chemins à espaces,
        # accolades et les dépôts multi-fichiers.
        self._on_drop(list(self.tk.splitlist(event.data)))

    def _set_drag(self, hover: bool) -> None:
        if self._drag_hover != hover:
            self._drag_hover = hover
            self._draw_border()

    # ── Cadre pointillé ───────────────────────────────────────────────────
    def _draw_border(self) -> None:
        c = self._border
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 * (_INSET + _RADIUS) or h < 2 * (_INSET + _RADIUS):
            return
        # ThemeService.color : la variante du mode courant — pair()[0]
        # cuirait la variante claire, fausse en thème sombre.
        color = (ThemeService.color("primary") if self._drag_hover
                 else ThemeService.color("border_strong"))
        m, r = _INSET, _RADIUS
        # Rectangle arrondi tracé à la main : coins doublés pour pincer la
        # courbe (smooth=True), le dash suit la ligne ainsi définie.
        pts = (
            m + r, m, w - m - r, m, w - m, m, w - m, m + r,
            w - m, h - m - r, w - m, h - m, w - m - r, h - m,
            m + r, h - m, m, h - m, m, h - m - r,
            m, m + r, m, m, m + r, m,
        )
        c.create_line(*pts, smooth=True, dash=(6, 4), width=2, fill=color,
                      joinstyle="round", capstyle="round")

    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self._border.configure(bg=tokens["surface"])
        self._title.configure(text_color=pair("heading"))
        self._sub.configure(text_color=pair("muted"))
        self._formats.configure(text_color=pair("faint"))
        self._meta.configure(text_color=pair("muted"))
        self._draw_border()


def _resample():
    """Resampling propre selon la version de Pillow."""
    try:
        from PIL import Image
        return Image.Resampling.LANCZOS
    except AttributeError:  # Pillow < 9.1
        from PIL import Image
        return Image.LANCZOS
