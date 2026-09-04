"""Frame scrollable dont la scrollbar n'apparaît que si nécessaire.

CTkScrollableFrame grille sa scrollbar une fois pour toutes, même quand
le contenu tient largement dans la vue — une scrollbar vide et inactive.
À chaque changement de géométrie, on compare la hauteur demandée du
contenu à celle du canvas : la scrollbar est retirée quand tout est
visible, re-gridée (mêmes options) sinon.

Structure interne (customtkinter) : CTkScrollableFrame EST le frame de
contenu — un tkinter.Frame posé dans le canvas (`_parent_frame` n'est que
l'enveloppe qui porte canvas + scrollbar). La hauteur utile est donc
`self.winfo_reqheight()`.
"""

import customtkinter as ctk

_POLL_MS = 250  # rafle les contenus dont la taille change sans Configure


class ScrollFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        # Configure du canvas (la vue change) et du contenu (self — posé
        # dans le canvas, sa hauteur suit ses enfants) déclenchent la
        # décision. add="+" : ne pas écraser les bindings internes.
        self._parent_canvas.bind("<Configure>", self._update_scrollbar,
                                 add="+")
        self.bind("<Configure>", self._update_scrollbar, add="+")
        # Filet de sécurité : détruire des enfants (vider la liste,
        # reconstruire un dialogue) ne génère aucun Configure — le frame
        # de contenu ne rétrécit pas d'une hauteur < à la vue. Un sondage
        # discret rattrape ces changements de hauteur demandée.
        self._poll_scrollbar()

    def _poll_scrollbar(self) -> None:
        if self.winfo_exists():
            self._update_scrollbar()
            self.after(_POLL_MS, self._poll_scrollbar)

    def _update_scrollbar(self, _event=None) -> None:
        if not self.winfo_exists():
            return
        visible = self._parent_canvas.winfo_height()
        if visible <= 1:
            return  # pas encore géométré : ne rien décider
        needed = self.winfo_reqheight()
        show = needed > visible
        if show != (self._scrollbar.winfo_manager() == "grid"):
            self._scrollbar.grid() if show else self._scrollbar.grid_remove()
