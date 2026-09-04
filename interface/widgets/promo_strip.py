"""Bandeau promotionnel — une marque à la fois, roulement automatique.

Rangée fine et discrète, pensée pour border la vue Convertir : point de
couleur de marque, nom, accroche, points de position et lien. Le widget
est muet — il reçoit des Promo (core/promos) et délègue l'ouverture du
lien au parent via on_open. start()/stop() suivent la visibilité : aucun
minuteur qui tourne pour un bandeau caché.
"""

import customtkinter as ctk

from core.i18n import t
from core.promos import BRAND_COLORS, BRAND_NAMES
from interface.theme.tokens import pair


class PromoStrip(ctk.CTkFrame):
    def __init__(self, master, promos, on_open,
                 interval_ms: int = 8000, **kw):
        super().__init__(master, fg_color=pair("surface"), border_width=1,
                         border_color=pair("border"), corner_radius=8, **kw)
        self._promos = promos
        self._on_open = on_open
        self._index = 0
        self._interval = interval_ms
        self._job: str | None = None

        self.grid_columnconfigure(2, weight=1)

        self._dot = ctk.CTkLabel(self, text="●", width=16)
        self._dot.grid(row=0, column=0, padx=(14, 0), pady=9)

        self._brand = ctk.CTkLabel(self, text="", width=0,
                                   font=ctk.CTkFont(size=12, weight="bold"))
        self._brand.grid(row=0, column=1, sticky="w", padx=(2, 10))

        self._message = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", wraplength=620,
            text_color=pair("muted"), font=ctk.CTkFont(size=12))
        self._message.grid(row=0, column=2, sticky="ew")

        dots = ctk.CTkFrame(self, fg_color="transparent")
        dots.grid(row=0, column=3, padx=(8, 0))
        self._dots = []
        for i in range(len(promos)):
            dot = ctk.CTkLabel(dots, text="●", text_color=pair("border"),
                               font=ctk.CTkFont(size=8))
            dot.grid(row=0, column=i, padx=2)
            dot.bind("<Button-1>", lambda _event, i=i: self.show(i))
            self._dots.append(dot)

        self._link = ctk.CTkButton(
            self, text=t("promo.learn_more"), width=120, height=28,
            fg_color="transparent", text_color=pair("primary"),
            hover_color=pair("primary_tint"), corner_radius=8,
            command=self._open,
        )
        self._link.grid(row=0, column=4, padx=(10, 12), pady=8)

        # Tout le bandeau est cliquable : les bindtags d'un enfant ne
        # remontent pas au frame, chaque label reçoit son propre bind.
        for widget in (self, self._dot, self._brand, self._message):
            widget.bind("<Button-1>", lambda _event: self._open())

        self._paint()

    # ── Roulement ─────────────────────────────────────────────────────────
    def show(self, index: int) -> None:
        self._index = index % len(self._promos)
        self._paint()

    def start(self) -> None:
        """(Re)démarre le roulement — appelé quand le bandeau redevient
        visible ; sans effet s'il tourne déjà."""
        if self._job is None and self.winfo_exists():
            self._job = self.after(self._interval, self._tick)

    def stop(self) -> None:
        """Suspend le roulement — bandeau caché : rien ne tourne."""
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _tick(self) -> None:
        self._job = None
        if not self.winfo_exists():
            return
        self.show(self._index + 1)
        self.start()

    def _open(self) -> None:
        self._on_open(self._promos[self._index].url)

    def _paint(self) -> None:
        promo = self._promos[self._index]
        color = BRAND_COLORS[promo.brand]
        self._dot.configure(text_color=color)
        self._brand.configure(text=BRAND_NAMES[promo.brand],
                              text_color=color)
        self._message.configure(text=t(promo.key))
        for i, dot in enumerate(self._dots):
            dot.configure(
                text_color=color if i == self._index else pair("border"))

    # ── Thème ─────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        self.configure(fg_color=pair("surface"), border_color=pair("border"))
        self._message.configure(text_color=pair("muted"))
        self._link.configure(text_color=pair("primary"),
                             hover_color=pair("primary_tint"))
        self._paint()
