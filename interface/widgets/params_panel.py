"""Panneau de réglages — construit depuis SPEC, un réglage = deux lignes.

Intitulé + valeur à droite, contrôle pleine largeur dessous, pastille « ? »
porte l'aide (remplace la colonne de documentation de la v2). Les valeurs
stockées sont les kwargs bruts du moteur : get_params() rend le jeu du
moteur actif (vtracer en couleur, Potrace en binaire), sans table de
conversion côté vue.

Libellés : SPEC porte des clés i18n (`params.<clé>`, `params.<clé>_help`,
`params.seg_<valeur>`), résolues via t() à la construction — la vue est
reconstruite au changement de langue, jamais traduite en place.

Les entrées marquées `advanced=True` ne s'affichent que si
l'interrupteur « Réglages avancés » (rangée hors SPEC, hors _controls)
est armé — leurs valeurs restent dans _values et dans get_params()
quelle que soit la visibilité, pour ne pas dévier des presets.

Widget muet : émet on_change(clé, valeur) et on_expert(bool).
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.widgets.tooltip import HelpDot

# Valeurs brutes des moteurs — les libellés restent courts pour tenir en
# rangée et viennent de params.seg_<valeur>.
_SEG_COLORS = ("color", "binary")
_SEG_HIERARCHY = ("stacked", "cutout")
_SEG_MODE = ("spline", "polygon", "none")

# Deux blocs, un par moteur, chacun masqué par visible_if : en noir et
# blanc le panneau ne montre QUE les réglages Potrace (turdsize,
# alphamax, opttolerance) — les curseurs vtracer n'ont aucun effet sur
# ce moteur, les cacher évite de régler dans le vide.
SPEC = [
    dict(key="colormode", default="color", kind="seg", options=_SEG_COLORS),
    dict(key="invert", default=False, kind="switch",
         visible_if=("colormode", "binary")),
    # ── Couleur (vtracer) ────────────────────────────────────────────────
    dict(key="hierarchical", default="stacked", kind="seg", options=_SEG_HIERARCHY,
         visible_if=("colormode", "color"), advanced=True),
    dict(key="color_precision", default=6, kind="slider", mn=1, mx=8, step=1, fmt="{:d}",
         visible_if=("colormode", "color")),
    dict(key="layer_difference", default=16, kind="slider", mn=1, mx=64, step=1, fmt="{:d}",
         visible_if=("colormode", "color")),
    dict(key="mode", default="spline", kind="seg", options=_SEG_MODE,
         visible_if=("colormode", "color"), advanced=True),
    dict(key="filter_speckle", default=4, kind="slider", mn=0, mx=16, step=1, fmt="{:d}",
         visible_if=("colormode", "color")),
    dict(key="corner_threshold", default=60, kind="slider", mn=0, mx=180, step=1,
         fmt="{:d}°", visible_if=("colormode", "color"), advanced=True),
    dict(key="length_threshold", default=4.0, kind="slider", mn=3.5, mx=10.0, step=0.5,
         fmt="{:.1f}", visible_if=("colormode", "color"), advanced=True),
    dict(key="splice_threshold", default=45, kind="slider", mn=0, mx=180, step=1,
         fmt="{:d}°", visible_if=("colormode", "color"), advanced=True),
    dict(key="max_iterations", default=10, kind="slider", mn=1, mx=20, step=1, fmt="{:d}",
         visible_if=("colormode", "color"), advanced=True),
    # ── Noir & blanc (Potrace) ───────────────────────────────────────────
    dict(key="turdsize", default=2, kind="slider", mn=0, mx=20, step=1, fmt="{:d}",
         visible_if=("colormode", "binary")),
    dict(key="alphamax", default=1.0, kind="slider", mn=0.0, mx=1.4, step=0.1,
         fmt="{:.1f}", visible_if=("colormode", "binary"), advanced=True),
    dict(key="opttolerance", default=0.2, kind="slider", mn=0.0, mx=1.0, step=0.05,
         fmt="{:.2f}", visible_if=("colormode", "binary"), advanced=True),
]

PATH_PRECISION = 3  # fixé : précision décimale des chemins (interne)


class ParamsPanel(ctk.CTkFrame):
    def __init__(self, master, on_change, on_expert=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_change = on_change
        self._on_expert_cb = on_expert
        self._loading = False  # True pendant set_params : pas de callback
        self._expert = False   # réglages avancés masqués par défaut
        # Valeurs par défaut dès la construction : tout réglage a toujours
        # une valeur, même si set_params() reçoit un dict partiel (preset
        # d'un autre moteur, surcharges CLI…).
        self._values: dict[str, object] = {
            item["key"]: item["default"] for item in SPEC
        }
        self._controls: dict[str, dict] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        for i, item in enumerate(SPEC):
            self._build_row(item, row=i * 2)
        self._build_expert_row(row=len(SPEC) * 2)
        for key, entry in self._controls.items():
            if entry["item"]["kind"] == "seg":
                self._restyle_seg(key)
        self._update_visibility()

    def _build_expert_row(self, row: int) -> None:
        # Hors _controls : invisible à set_params/get_params/_update_visibility —
        # c'est un réglage de vue, pas un kwarg moteur.
        self._sep = ctk.CTkFrame(self, height=1, fg_color=pair("border"))
        self._sep.grid(row=row, column=0, columnspan=2, sticky="ew",
                       pady=(16, 0))
        self._expert_switch = ctk.CTkSwitch(
            self, text=t("params.expert"), cursor="hand2",
            font=ctk.CTkFont(size=11),
            progress_color=pair("primary"), button_color=pair("on_primary"),
            button_hover_color=pair("on_primary"),
            command=self._on_expert,
        )
        self._expert_switch.grid(row=row + 1, column=0, columnspan=2,
                                 sticky="w", pady=(10, 0))

    # ── Construction ──────────────────────────────────────────────────────
    def _build_row(self, item: dict, row: int) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        frame.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)

        name = ctk.CTkLabel(
            head, text=t(f"params.{item['key']}").upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=pair("muted"), anchor="w",
        )
        name.grid(row=0, column=0, sticky="w")
        HelpDot(head, t(f"params.{item['key']}_help")).grid(
            row=0, column=1, padx=(6, 0))

        ctrl_box = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl_box.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ctrl_box.grid_columnconfigure(0, weight=1)

        self._controls[item["key"]] = dict(item=item, frame=frame, head=head,
                                           box=ctrl_box, value=None, ctl=None)

        if item["kind"] == "seg":
            value = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=10),
                                 text_color=pair("faint"))
            value.grid(row=0, column=2, padx=(8, 0))
            self._controls[item["key"]]["value"] = value
            self._build_seg(item, ctrl_box)
        elif item["kind"] == "switch":
            self._build_switch(item, ctrl_box)
        else:
            value = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=10),
                                 text_color=pair("muted"))
            value.grid(row=0, column=2, padx=(8, 0))
            self._controls[item["key"]]["value"] = value
            self._build_slider(item, ctrl_box)

    def _build_seg(self, item: dict, box) -> None:
        holder = ctk.CTkFrame(box, fg_color="transparent")
        holder.grid(row=0, column=0, sticky="ew")
        buttons = {}
        last = len(item["options"]) - 1
        for j, raw in enumerate(item["options"]):
            # Parts égales + sticky ew : les segments remplissent la carte,
            # comme les curseurs — pas de rangée raccourcie à gauche.
            holder.grid_columnconfigure(j, weight=1)
            btn = ctk.CTkButton(
                holder, text=t(f"params.seg_{raw}"), width=0, height=28,
                corner_radius=6,
                font=ctk.CTkFont(size=11), cursor="hand2",
                command=lambda v=raw: self._on_seg(item["key"], v),
            )
            btn.grid(row=0, column=j,
                     padx=(0, 0 if j == last else 6), sticky="ew")
            buttons[raw] = btn
        self._controls[item["key"]]["ctl"] = buttons

    def _build_switch(self, item: dict, box) -> None:
        sw = ctk.CTkSwitch(
            box, text="", width=44, height=20, switch_width=36, switch_height=18,
            progress_color=pair("primary"), button_color=pair("on_primary"),
            button_hover_color=pair("on_primary"),
            command=lambda: self._on_switch(item["key"]),
        )
        sw.grid(row=0, column=0, sticky="w")
        self._controls[item["key"]]["ctl"] = sw

    def _build_slider(self, item: dict, box) -> None:
        steps = max(1, round((item["mx"] - item["mn"]) / item["step"]))
        slider = ctk.CTkSlider(
            box, from_=item["mn"], to=item["mx"], number_of_steps=steps,
            height=18, button_length=14, button_corner_radius=7, border_width=0,
            command=lambda v: self._on_slider(item["key"], v),
        )
        slider.grid(row=0, column=0, sticky="ew")
        self._controls[item["key"]]["ctl"] = slider

    # ── Handlers internes ─────────────────────────────────────────────────
    def _on_seg(self, key: str, raw) -> None:
        if self._loading or self._values.get(key) == raw:
            return
        self._values[key] = raw
        self._restyle_seg(key)
        if key == "colormode":
            self._update_visibility()
        self._on_change(key, raw)

    def _on_switch(self, key: str) -> None:
        if self._loading:
            return
        raw = bool(self._controls[key]["ctl"].get())
        self._values[key] = raw
        self._on_change(key, raw)

    def _on_slider(self, key: str, value: float) -> None:
        if self._loading:
            return
        item = self._controls[key]["item"]
        raw = self._snap(item, value)
        self._values[key] = raw
        self._controls[key]["value"].configure(text=item["fmt"].format(raw))
        self._on_change(key, raw)

    @staticmethod
    def _snap(item: dict, value: float) -> object:
        # La commande CTkSlider émet la valeur réelle (entre mn et mx) :
        # quantifier sur le pas, borne, puis typer (int si pas entier).
        v = round((value - item["mn"]) / item["step"]) * item["step"] + item["mn"]
        v = min(item["mx"], max(item["mn"], v))
        return round(v) if item["step"] >= 1 else round(v, 2)

    # ── Apparence des segments ────────────────────────────────────────────
    def _restyle_seg(self, key: str) -> None:
        entry = self._controls[key]
        buttons = entry["ctl"]
        labels = {raw: t(f"params.seg_{raw}")
                  for raw in entry["item"]["options"]}
        for raw, btn in buttons.items():
            active = raw == self._values.get(key)
            btn.configure(
                fg_color=pair("primary") if active else "transparent",
                hover_color=pair("primary_hover") if active else pair("seg_track"),
                text_color=pair("on_primary") if active else pair("muted"),
                border_width=0 if active else 1,
                border_color=pair("border"),
            )
        if entry["value"] is not None:
            entry["value"].configure(text=labels[self._values.get(key)])

    def _update_visibility(self) -> None:
        for key, entry in self._controls.items():
            item = entry["item"]
            cond = item.get("visible_if")
            show = cond is None or self._values.get(cond[0]) == cond[1]
            if item.get("advanced"):
                show = show and self._expert
            entry["frame"].grid() if show else entry["frame"].grid_remove()

    # ── API ───────────────────────────────────────────────────────────────
    def set_params(self, params: dict) -> None:
        """Applique des kwargs bruts du moteur actif (+ « invert ») sans callback."""
        self._loading = True
        try:
            for key, entry in self._controls.items():
                if key not in params:
                    continue
                raw = params[key]
                item = entry["item"]
                self._values[key] = raw
                if item["kind"] == "seg":
                    self._restyle_seg(key)
                elif item["kind"] == "switch":
                    entry["ctl"].select() if raw else entry["ctl"].deselect()
                else:
                    # set() attend la valeur réelle, pas une fraction 0-1.
                    entry["ctl"].set(raw)
                    entry["value"].configure(text=item["fmt"].format(raw))
        finally:
            self._loading = False
        self._update_visibility()

    def get_params(self) -> dict:
        """Kwargs bruts du moteur actif (invert exclu : traité à la
        préparation) — binaire → Potrace, couleur → vtracer."""
        if self._values["colormode"] == "binary":
            return dict(
                colormode="binary",
                turdsize=self._values["turdsize"],
                alphamax=self._values["alphamax"],
                opttolerance=self._values["opttolerance"],
                path_precision=PATH_PRECISION,
            )
        return dict(
            colormode="color",
            hierarchical=self._values["hierarchical"],
            mode=self._values["mode"],
            filter_speckle=self._values["filter_speckle"],
            color_precision=self._values["color_precision"],
            layer_difference=self._values["layer_difference"],
            corner_threshold=self._values["corner_threshold"],
            length_threshold=self._values["length_threshold"],
            splice_threshold=self._values["splice_threshold"],
            max_iterations=self._values["max_iterations"],
            path_precision=PATH_PRECISION,
        )

    def get_invert(self) -> bool:
        return bool(self._values.get("invert", False))

    # ── Réglages avancés ─────────────────────────────────────────────────
    def set_expert(self, enabled: bool) -> None:
        """Positionne l'interrupteur sans émettre on_expert (restauration)."""
        self._expert = bool(enabled)
        self._expert_switch.select() if enabled else self._expert_switch.deselect()
        self._update_visibility()

    def is_expert(self) -> bool:
        return self._expert

    def _on_expert(self) -> None:
        self._expert = bool(self._expert_switch.get())
        self._update_visibility()  # aucune valeur moteur ne change
        if self._on_expert_cb is not None:
            self._on_expert_cb(self._expert)

    # ── Thème ─────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        # pair() partout : ne jamais figer un hex simple.
        self._sep.configure(fg_color=pair("border"))
        self._expert_switch.configure(
            progress_color=pair("primary"),
            button_color=pair("on_primary"),
            button_hover_color=pair("on_primary"),
        )
        for key, entry in self._controls.items():
            if entry["item"]["kind"] == "seg":
                self._restyle_seg(key)
            elif entry["item"]["kind"] == "switch":
                entry["ctl"].configure(
                    progress_color=pair("primary"),
                    button_color=pair("on_primary"),
                    button_hover_color=pair("on_primary"),
                )
            else:
                entry["ctl"].configure(
                    progress_color=pair("primary"),
                    button_color=pair("primary"),
                    button_hover_color=pair("primary_hover"),
                )
