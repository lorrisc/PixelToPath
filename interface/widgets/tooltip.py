"""Info-bulles : point d'aide « ? » + bulle différé.

Remplace la colonne de documentation de l'ancienne LeftFrame : l'aide vit
au plus près du réglage concerné. Couleurs lues au moment de l'affichage
(toujours dans le bon thème, sans protocole apply_theme).
"""

import tkinter as tk

import customtkinter as ctk

from interface.theme.tokens import ThemeService, pair

_DELAY_MS = 450
_WRAP = 240


class Tooltip:
    """Bulle attachée à un widget (affichée sous lui après délai)."""

    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _e=None):
        self._cancel()
        self._job = self._widget.after(_DELAY_MS, self._show)

    def _cancel(self):
        if self._job is not None:
            self._widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        if self._tip is not None or not self._text:
            return
        tokens = ThemeService.tokens()
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6

        self._tip = ctk.CTkToplevel(self._widget)
        self._tip.overrideredirect(True)
        self._tip.attributes("-topmost", True)
        # fenêtre 1x1 le temps du mesurage, puis positionnée
        self._tip.geometry("+1+1")

        ctk.CTkLabel(
            self._tip, text=self._text, justify="left", wraplength=_WRAP,
            font=ctk.CTkFont(size=10),
            fg_color=tokens["tooltip_bg"], text_color=tokens["tooltip_text"],
            corner_radius=6,
        ).pack(padx=1, pady=1)

        self._tip.update_idletasks()
        w = self._tip.winfo_reqwidth()
        sw = self._widget.winfo_screenwidth()
        x = max(8, min(x - w // 2, sw - w - 8))
        self._tip.geometry(f"+{x}+{y}")

    def _hide(self, _e=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                # Bulle déjà détruite en cascade (changement de langue :
                # les vues et leurs Toplevel sont reconstruits sous le
                # curseur) — rien à faire.
                pass
            self._tip = None


class HelpDot(ctk.CTkLabel):
    """Pastille « ? » — porte une info-bulle sur le réglage voisin."""

    def __init__(self, master, text: str):
        super().__init__(
            master, text="?", width=16, height=16,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=pair("faint"),
            cursor="hand2",
        )
        self.bind("<Enter>", lambda _e: self.configure(text_color=pair("primary")))
        self.bind("<Leave>", lambda _e: self.configure(text_color=pair("faint")))
        Tooltip(self, text)

    def apply_theme(self, tokens: dict) -> None:
        self.configure(text_color=pair("faint"))
