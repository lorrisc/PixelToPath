"""Carrousel d'images — défilement automatique, points cliquables.

Muets : on lui donne des paires (CTkImage, légende) et un intervalle ; un
clic sur l'image passe à la suivante, un clic sur un point y saute. Le
minuteur ne se re-programme que tant que le widget existe — détruit, la
boucle s'arrête d'elle-même.
"""

import customtkinter as ctk

from interface.theme.tokens import pair


class Carousel(ctk.CTkFrame):
    def __init__(self, master, slides, interval_ms: int = 4500, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._slides = slides
        self._index = 0
        self._interval = interval_ms
        self._job: str | None = None

        self.grid_columnconfigure(0, weight=1)

        # Capture cerclée d'une bordure : une image claire posée sur une
        # carte sombre « flotte » sans séparateur.
        self._frame = ctk.CTkFrame(self, fg_color=pair("surface"),
                                   border_width=1,
                                   border_color=pair("border"),
                                   corner_radius=8)
        self._frame.grid(row=0, column=0)
        image, _caption = slides[0]
        self._image = ctk.CTkLabel(self._frame, image=image, text="")
        self._image.grid(row=0, column=0, padx=1, pady=1)
        self._image.bind("<Button-1>", lambda _event: self.next())

        self._caption = ctk.CTkLabel(self, text=_caption, justify="center",
                                     text_color=pair("muted"),
                                     font=ctk.CTkFont(size=11),
                                     wraplength=640)
        self._caption.grid(row=1, column=0, pady=(8, 0))

        dots = ctk.CTkFrame(self, fg_color="transparent")
        dots.grid(row=2, column=0, pady=(6, 0))
        self._dots = []
        for i in range(len(slides)):
            dot = ctk.CTkLabel(dots, text="●", text_color=pair("border"),
                               font=ctk.CTkFont(size=10))
            dot.grid(row=0, column=i, padx=3)
            dot.bind("<Button-1>", lambda _event, i=i: self.show(i))
            self._dots.append(dot)

        self._paint()
        self._schedule()

    # ── Navigation ────────────────────────────────────────────────────────
    def next(self) -> None:
        self.show(self._index + 1)

    def show(self, index: int) -> None:
        self._index = index % len(self._slides)
        self._paint()

    # ── Minuteur ──────────────────────────────────────────────────────────
    def _schedule(self) -> None:
        self._job = self.after(self._interval, self._tick)

    def _tick(self) -> None:
        self._job = None
        if not self.winfo_exists():
            return
        self.next()
        self._schedule()

    def _paint(self) -> None:
        image, caption = self._slides[self._index]
        self._image.configure(image=image)
        self._caption.configure(text=caption)
        for i, dot in enumerate(self._dots):
            active = i == self._index
            dot.configure(text_color=pair("primary" if active else "border"))

    # ── Thème ─────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        self._frame.configure(fg_color=pair("surface"),
                              border_color=pair("border"))
        self._caption.configure(text_color=pair("muted"))
        self._paint()
