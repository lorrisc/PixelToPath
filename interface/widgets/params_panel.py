"""Panneau de réglages — construit depuis SPEC, un réglage = deux lignes.

Intitulé + valeur à droite, contrôle pleine largeur dessous, pastille « ? »
porte l'aide (remplace la colonne de documentation de la v2). Les valeurs
stockées sont les kwargs vtracer bruts : get_params() les rend tel quel au
moteur, sans table de conversion côté vue.

Libellés : SPEC porte des clés i18n (`params.<clé>`, `params.<clé>_help`,
`params.seg_<valeur>`), résolues via t() à la construction — la vue est
reconstruite au changement de langue, jamais traduite en place.

Widget muet : émet on_change(clé, valeur).
"""

import customtkinter as ctk

from core.i18n import t
from interface.theme.tokens import pair
from interface.widgets.tooltip import HelpDot

# Valeurs brutes vtracer — les libellés restent courts pour tenir en rangée
# et viennent de params.seg_<valeur>.
_SEG_COLORS = ("color", "binary")
_SEG_HIERARCHY = ("stacked", "cutout")
_SEG_MODE = ("spline", "polygon", "none")

SPEC = [
    dict(key="colormode", default="color", kind="seg", options=_SEG_COLORS),
    dict(key="invert", default=False, kind="switch",
         visible_if=("colormode", "binary")),
    dict(key="hierarchical", default="stacked", kind="seg", options=_SEG_HIERARCHY,
         visible_if=("colormode", "color")),
    dict(key="color_precision", default=6, kind="slider", mn=1, mx=8, step=1, fmt="{:d}",
         visible_if=("colormode", "color")),
    dict(key="layer_difference", default=16, kind="slider", mn=1, mx=64, step=1, fmt="{:d}",
         visible_if=("colormode", "color")),
    dict(key="mode", default="spline", kind="seg", options=_SEG_MODE),
    dict(key="filter_speckle", default=4, kind="slider", mn=0, mx=16, step=1, fmt="{:d}"),
    dict(key="corner_threshold", default=60, kind="slider", mn=0, mx=180, step=1, fmt="{:d}°"),
    dict(key="length_threshold", default=4.0, kind="slider", mn=3.5, mx=10.0, step=0.5,
         fmt="{:.1f}"),
    dict(key="splice_threshold", default=45, kind="slider", mn=0, mx=180, step=1, fmt="{:d}°"),
    dict(key="max_iterations", default=10, kind="slider", mn=1, mx=20, step=1, fmt="{:d}"),
]

PATH_PRECISION = 3  # fixé : précision décimale des chemins (interne)


class ParamsPanel(ctk.CTkFrame):
    def __init__(self, master, on_change, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_change = on_change
        self._loading = False  # True pendant set_params : pas de callback
        # Valeurs par défaut dès la construction (vtracer) : tout réglage a
        # toujours une valeur, même si set_params() reçoit un dict partiel
        # (preset binaire sans les réglages couleur, surcharges CLI…).
        self._values: dict[str, object] = {
            item["key"]: item["default"] for item in SPEC
        }
        self._controls: dict[str, dict] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        for i, item in enumerate(SPEC):
            self._build_row(item, row=i * 2)
        for key, entry in self._controls.items():
            if entry["item"]["kind"] == "seg":
                self._restyle_seg(key)
        self._update_visibility()

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
            cond = entry["item"].get("visible_if")
            show = cond is None or self._values.get(cond[0]) == cond[1]
            entry["frame"].grid() if show else entry["frame"].grid_remove()

    # ── API ───────────────────────────────────────────────────────────────
    def set_params(self, params: dict) -> None:
        """Applique des kwargs vtracer bruts (+ « invert ») sans callback."""
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
        """Kwargs vtracer bruts (invert exclu : traité à la préparation)."""
        p = dict(
            colormode=self._values["colormode"],
            mode=self._values["mode"],
            filter_speckle=self._values["filter_speckle"],
            corner_threshold=self._values["corner_threshold"],
            length_threshold=self._values["length_threshold"],
            splice_threshold=self._values["splice_threshold"],
            max_iterations=self._values["max_iterations"],
            path_precision=PATH_PRECISION,
        )
        if p["colormode"] == "color":
            p["hierarchical"] = self._values["hierarchical"]
            p["color_precision"] = self._values["color_precision"]
            p["layer_difference"] = self._values["layer_difference"]
        return p

    def get_invert(self) -> bool:
        return bool(self._values.get("invert", False))

    # ── Thème ─────────────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        # pair() partout : ne jamais figer un hex simple.
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
