"""Vue Batch (Pro) — file de fichiers → dossier de sortie, une thread.

Trois colonnes : 01 · Fichiers (liste + destination) → 02 · Réglages
(presets + paramètres vtracer, éditables ici comme dans Convertir) →
03 · Aperçu (rendu vectoriel du fichier sélectionné).

Orchestration uniquement : les items sont soumis au ConversionWorker
(ctx.worker, partagé avec le hot folder), les résultats reviennent via
after(0). L'aperçu vit sur SA propre thread — source réduite à
_PREVIEW_MAX px, un seul calcul à la fois (_pv_busy/_pv_dirty), debounce
et cache LRU — cliquer dans autant de fichiers qu'on veut ne fige jamais
l'UI et ne concurrence pas la conversion.
"""

import itertools
import os
import threading
from collections import OrderedDict
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image
from tkinterdnd2 import DND_FILES

from core.constants import IMG_EXTS
from core.convert_service import (
    ConversionWorker,
    convert_file,
    new_temp_path,
    next_output_path,
    prepare_input,
    render_svg_to_pil,
)
from core.i18n import t, tp
from interface.theme.tokens import pair
from interface.utils import open_directory
from interface.views import View
from interface.widgets.card import Card, GhostButton, SectionHeader
from interface.widgets.dialogs import ManagePresetsDialog, SavePresetDialog
from interface.widgets.params_panel import ParamsPanel
from interface.widgets.preset_picker import PresetPicker, custom_label
from interface.widgets.preview_canvas import PreviewCanvas
from interface.widgets.scrollframe import ScrollFrame

_DEBOUNCE_MS = 350    # frappe de réglage → recalcul de l'aperçu
_PREVIEW_MAX = 640    # plus grand côté de la source d'aperçu (perf vtracer)
_CACHE_MAX = 8        # aperçus gardés en mémoire (SVG temporaire + PIL)


def _filetypes():
    """Filtres du sélecteur — résolus à l'appel (jamais à l'import)."""
    return [
        (t("common.filetype_images"), " ".join(IMG_EXTS)),
        (t("common.filetype_all"), "*.*"),
    ]


class BatchView(View):
    def __init__(self, master, ctx):
        super().__init__(master, ctx)
        self._items: list[dict] = []
        self._paths_seen: set[str] = set()
        self._ids = itertools.count(1)
        self._listening = False
        self._running = False
        self._done = 0
        self._total = 0
        self._out_dir = ctx.config.get("batch", "last_output_dir", "")
        self._selected_id = None
        self._compare_active = False

        # Aperçu : au plus un calcul en vol (_pv_busy) ; un changement de
        # sélection/réglage pendant le cours note _pv_dirty et est recalculé
        # juste après — jamais de cascade de threads vtracer.
        self._pv_job = None
        self._pv_busy = False
        self._pv_dirty = False
        self._pv_cache: OrderedDict = OrderedDict()

        # Preset actif persisté ; réglages appliqués sans aperçu (rien
        # n'est encore sélectionné).
        self._presets = ctx.presets
        key = ctx.config.get("batch", "preset", "bw")
        if self._presets.params(key) is None:
            key = "bw"

        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=3, uniform="cols")
        self.grid_columnconfigure(2, weight=4, uniform="cols")
        self.grid_rowconfigure(1, weight=1)

        SectionHeader(self, t("batch.title")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        self._build_files_column()
        self._build_settings_column()
        self._build_preview_column()
        self._build_footer()

        self._apply_preset(key, schedule=False)

        # Dépôt multi-fichiers sur toute la vue et sur la liste.
        for target in (self, self._list, self._empty):
            target.drop_target_register(DND_FILES)
            target.dnd_bind(
                "<<Drop>>",
                lambda e: self._add_paths(list(self.tk.splitlist(e.data))),
            )

    # ── Construction ──────────────────────────────────────────────────────
    def _build_files_column(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        col.grid_rowconfigure(2, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("batch.files")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self._controls_card = Card(col)
        self._controls_card.grid(row=1, column=0, sticky="ew")
        self._controls_card.grid_columnconfigure(0, weight=1)
        self._build_controls(self._controls_card)

        self._build_list(col)

    def _build_controls(self, card: Card) -> None:
        row_out = ctk.CTkFrame(card, fg_color="transparent")
        row_out.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        row_out.grid_columnconfigure(0, weight=1)
        self._out_entry = ctk.CTkEntry(row_out, height=30,
                                       placeholder_text=t("batch.out_placeholder"))
        self._out_entry.grid(row=0, column=0, sticky="ew")
        self._out_entry.insert(0, self._out_dir)
        self._out_entry.configure(state="disabled")
        GhostButton(row_out, text=t("common.browse"), width=96, height=30,
                    command=self._pick_out_dir).grid(row=0, column=1,
                                                     padx=(8, 0))

        row_actions = ctk.CTkFrame(card, fg_color="transparent")
        row_actions.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 12))
        self._btn_add_files = GhostButton(
            row_actions, text=t("batch.add_files"), width=150, height=30,
            command=self._pick_files)
        self._btn_add_files.pack(side="left")
        self._btn_add_dir = GhostButton(
            row_actions, text=t("batch.add_dir"), width=140, height=30,
            command=self._pick_dir)
        self._btn_add_dir.pack(side="left", padx=(8, 0))
        self._btn_clear = GhostButton(row_actions, text=t("batch.clear"),
                                      width=70, height=30, command=self._clear)
        self._btn_clear.pack(side="right")
        self._count_lbl = ctk.CTkLabel(row_actions,
                                       text=tp("batch.count", 0),
                                       text_color=pair("faint"),
                                       font=ctk.CTkFont(size=11))
        self._count_lbl.pack(side="right", padx=(0, 10))

    def _build_list(self, col) -> None:
        self._list = ScrollFrame(col, fg_color=pair("surface"))
        self._list.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self._empty = ctk.CTkLabel(
            self._list, justify="center", text_color=pair("faint"),
            text=t("batch.empty"),
        )
        self._empty.pack(pady=32, fill="x", expand=True)

    def _build_settings_column(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=1, sticky="nsew", padx=(0, 12))
        col.grid_rowconfigure(1, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("batch.settings")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        card = Card(col)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_rowconfigure(2, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # Puces de presets + actions, comme dans Convertir : « Enregistrer »
        # ne s'active qu'en état Personnalisé, « Gérer » ouvre renommage/
        # suppression. Les presets nourrissent aussi le hot folder et la CLI.
        picker_row = ctk.CTkFrame(card, fg_color="transparent")
        picker_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        picker_row.grid_columnconfigure(0, weight=1)
        self._picker = PresetPicker(picker_row, on_select=self._on_preset)
        self._picker.grid(row=0, column=0, sticky="ew")
        self._btn_save_preset = GhostButton(
            picker_row, text=t("common.save"), width=92, height=30,
            state="disabled", command=self._on_save_preset,
        )
        self._btn_save_preset.grid(row=0, column=1, padx=(8, 0))
        self._btn_manage_presets = GhostButton(
            picker_row, text=t("common.manage"), width=56, height=30,
            command=self._on_manage_presets,
        )
        self._btn_manage_presets.grid(row=0, column=2, padx=(6, 0))

        ctk.CTkFrame(card, height=1, corner_radius=0,
                     fg_color=pair("border")).grid(
            row=1, column=0, sticky="ew", padx=14
        )

        scroller = ScrollFrame(card, fg_color="transparent")
        scroller.grid(row=2, column=0, sticky="nsew", padx=4, pady=(2, 6))
        # Poids sur le frame scrollé (voir Convertir) : le panneau suit la
        # largeur de la carte au lieu de sa largeur demandée.
        scroller.grid_columnconfigure(0, weight=1)
        self._params = ParamsPanel(scroller, on_change=self._on_params_change,
                                   on_expert=self._on_expert)
        self._params.grid(row=0, column=0, sticky="nsew", padx=8)
        # Préférence « Réglages avancés » partagée avec la vue Convertir.
        self._params.set_expert(bool(
            self.ctx.config.get("convert", "expert_params", False)))

    def _build_preview_column(self) -> None:
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=1, column=2, sticky="nsew")
        col.grid_rowconfigure(1, weight=1)
        col.grid_columnconfigure(0, weight=1)

        SectionHeader(col, t("batch.preview")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        card = Card(col)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._preview = PreviewCanvas(
            card, empty_text=t("batch.preview_empty"),
        )
        self._preview.grid(row=0, column=0, sticky="nsew", padx=16, pady=(14, 6))

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", padx=16, pady=(6, 14))
        self._pv_info = ctk.CTkLabel(footer, text="", anchor="w",
                                     text_color=pair("muted"),
                                     font=ctk.CTkFont(size=11))
        self._pv_info.pack(side="left", fill="x", expand=True)
        self._btn_compare = GhostButton(footer, text=t("common.compare"),
                                        width=90, height=34,
                                        command=self._toggle_compare)
        self._btn_compare.pack(side="left")
        self._btn_1_1 = GhostButton(footer, text="1:1", width=52, height=34,
                                    command=self._preview.zoom_1_1)
        self._btn_1_1.pack(side="left", padx=(8, 0))
        self._btn_fit = GhostButton(footer, text=t("common.fit"), width=80,
                                    height=34, command=self._preview.fit)
        self._btn_fit.pack(side="left", padx=(8, 0))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        footer.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(footer, height=8,
                                            corner_radius=4)
        self._progress.set(0)
        self._progress.grid(row=0, column=0, sticky="ew")

        info = ctk.CTkFrame(footer, fg_color="transparent")
        info.grid(row=1, column=0, sticky="ew")
        self._progress_lbl = ctk.CTkLabel(info, text="0 / 0",
                                          text_color=pair("faint"),
                                          font=ctk.CTkFont(size=11))
        self._progress_lbl.pack(side="left")
        # La destination reste visible PENDANT et APRÈS le lot : c'est ici
        # (et via « Ouvrir le dossier ») qu'on sait où vont les SVG.
        self._dest_lbl = ctk.CTkLabel(info, text="", anchor="w",
                                      text_color=pair("faint"),
                                      font=ctk.CTkFont(size=11))
        self._dest_lbl.pack(side="left", padx=(14, 0))

        self._btn_open_dir = GhostButton(footer, text=t("batch.open_dir"),
                                         width=140, height=34,
                                         state="disabled",
                                         command=self._open_out_dir)
        self._btn_open_dir.grid(row=0, column=1, rowspan=2, padx=(12, 0),
                                sticky="e")
        self._btn_launch = ctk.CTkButton(footer, text=t("batch.launch"),
                                         width=120, height=34,
                                         command=self._launch)
        self._btn_launch.grid(row=0, column=2, rowspan=2, padx=(8, 0),
                              sticky="e")
        self._btn_cancel = GhostButton(footer, text=t("common.cancel"),
                                       width=90, height=34, state="disabled",
                                       command=self._cancel)
        self._btn_cancel.grid(row=0, column=3, rowspan=2, padx=(8, 0),
                              sticky="e")

        if self._out_dir:
            self._btn_open_dir.configure(state="normal")
            self._dest_lbl.configure(
                text=t("common.destination", dir=self._out_dir))

    # ── Sélections ────────────────────────────────────────────────────────
    def _on_preset(self, label: str) -> None:
        key = self._presets.resolve(label)
        if key is not None:
            self._apply_preset(key)

    def _apply_preset(self, key: str, schedule: bool = True) -> None:
        self._preset_key = key
        self._refresh_picker(self._presets.display_name(key))
        params = self._presets.params(key)
        params["invert"] = False
        self._params.set_params(params)
        self._btn_save_preset.configure(state="disabled")
        if schedule:
            self.ctx.config.set("batch", "preset", key)
            self._request_preview()

    def _refresh_picker(self, active_display: str | None) -> None:
        self._picker.set_options(
            [self._presets.display_name(k) for k in self._presets.keys()],
            active=active_display,
        )

    def _on_params_change(self, _key, _value) -> None:
        # Réglage manuel : le preset correspondant est recalculé — s'il n'y
        # en a plus, l'état devient « Personnalisé » et Enregistrer s'arme.
        self._sync_preset_state()
        self._request_preview()

    def _on_expert(self, enabled: bool) -> None:
        # Préférence de vue, partagée avec la vue Convertir.
        self.ctx.config.set("convert", "expert_params", enabled)

    def _sync_preset_state(self) -> None:
        """Puces + bouton Enregistrer d'après les réglages courants."""
        key = self._presets.matching(self._params.get_params())
        if key is None:
            self._preset_key = None
            self._refresh_picker(custom_label())
            self._btn_save_preset.configure(state="normal")
        else:
            self._preset_key = key
            self._refresh_picker(self._presets.display_name(key))
            self._btn_save_preset.configure(state="disabled")

    def _on_save_preset(self) -> None:
        if self._preset_key is not None:
            return
        SavePresetDialog(self, self.ctx, self._params.get_params(),
                         on_saved=self._on_preset_saved)

    def _on_preset_saved(self, name: str) -> None:
        key = self._presets.resolve(name)
        self._preset_key = key
        self._refresh_picker(name)
        self._btn_save_preset.configure(state="disabled")
        self.ctx.config.set("batch", "preset", key)
        self.ctx.status.set_status(t("presets.saved", name=name), "ok")

    def _on_manage_presets(self) -> None:
        ManagePresetsDialog(self, self.ctx, on_changed=self._sync_preset_state)

    def _pick_files(self) -> None:
        names = filedialog.askopenfilenames(
            parent=self, title=t("batch.pick_files_title"),
            filetypes=_filetypes())
        self._add_paths(names)

    def _pick_dir(self) -> None:
        d = filedialog.askdirectory(parent=self, title=t("batch.pick_dir_title"))
        if d:
            self._add_paths([d])

    def _pick_out_dir(self) -> None:
        d = filedialog.askdirectory(parent=self, title=t("batch.out_title"),
                                    initialdir=self._out_dir or os.path.expanduser("~"))
        if d:
            self._set_out_dir(d)
            # Choisir un dossier ici le propose aussi comme source : les
            # images qu'il contient sont importées comme via « Ajouter un
            # dossier » (doublons filtrés par _paths_seen).
            self._add_paths([d])

    def _set_out_dir(self, d: str) -> None:
        self._out_dir = d
        self._out_entry.configure(state="normal")
        self._out_entry.delete(0, "end")
        self._out_entry.insert(0, d)
        self._out_entry.configure(state="disabled")
        self._btn_open_dir.configure(state="normal")
        self._dest_lbl.configure(text=t("common.destination", dir=d))
        self.ctx.config.set("batch", "last_output_dir", d)

    def _open_out_dir(self) -> None:
        if not self._out_dir:
            return
        if not open_directory(self._out_dir):
            self.ctx.status.set_status(t("batch.out_missing"), "error")

    # ── Items ─────────────────────────────────────────────────────────────
    def _add_paths(self, paths) -> None:
        added = 0
        for raw in paths:
            p = os.path.normpath(raw)
            if os.path.isdir(p):
                # Récursif : on dépose une bibliothèque, pas un plat de fichiers.
                candidates = sorted(
                    os.path.join(root, name)
                    for root, _dirs, names in os.walk(p)
                    for name in names
                    if os.path.splitext(name)[1].lower() in IMG_EXTS
                )
            elif os.path.splitext(p)[1].lower() in IMG_EXTS:
                candidates = [p]
            else:
                continue
            for c in candidates:
                if c in self._paths_seen:
                    continue
                self._paths_seen.add(c)
                self._append_row(c)
                added += 1
        if added:
            self._refresh_count()
            self.ctx.status.set_status(tp("batch.added", added), "idle")
            if self._selected_id is None:
                self._select(self._items[0]["id"])  # aperçu immédiat

    def _append_row(self, path: str) -> None:
        if not self._items:
            self._empty.pack_forget()
        item = {
            "id": ("batch", next(self._ids)),  # préfixe : cohabitation hot folder
            "path": path,
            "thumb": self._make_thumb(path),
            # Code d'état (jamais un libellé traduit) : la comparaison et le
            # re-habillage thème restent corrects après un changement de langue.
            "status": "waiting",
            "out": None,
        }
        row = ctk.CTkFrame(self._list, fg_color="transparent", height=56,
                           cursor="hand2")
        row.pack(fill="x", pady=2)
        row.drop_target_register(DND_FILES)
        row.dnd_bind(
            "<<Drop>>",
            lambda e: self._add_paths(list(self.tk.splitlist(e.data))),
        )
        thumb_lbl = ctk.CTkLabel(row, image=item["thumb"], text="")
        thumb_lbl.pack(side="left", padx=(4, 10), pady=4)
        name_lbl = ctk.CTkLabel(row, text=os.path.basename(path),
                                anchor="w", text_color=pair("text"))
        name_lbl.pack(side="left", fill="x", expand=True)
        status_lbl = ctk.CTkLabel(row, text=t("batch.status.waiting"),
                                  anchor="e",
                                  text_color=pair("faint"),
                                  font=ctk.CTkFont(size=11))
        status_lbl.pack(side="left", padx=(10, 8))
        btn = GhostButton(row, text="✕", width=28, height=24,
                          command=lambda: self._remove(item["id"]))
        btn.pack(side="right")
        # Un clic sélectionne la ligne → aperçu à droite.
        for widget in (row, thumb_lbl, name_lbl, status_lbl):
            widget.bind("<Button-1>",
                        lambda _e, i=item["id"]: self._select(i))
        item.update(row=row, name_lbl=name_lbl, status_lbl=status_lbl,
                    btn=btn)
        self._items.append(item)

    def _make_thumb(self, path: str):
        try:
            with Image.open(path) as img:
                thumb = img.convert("RGB")
                thumb.thumbnail((48, 48))
        except Exception:
            return None  # vignette impossible : la conversion dira pourquoi
        return ctk.CTkImage(light_image=thumb, dark_image=thumb,
                            size=(thumb.width, thumb.height))

    def _select(self, item_id) -> None:
        if item_id == self._selected_id:
            return
        self._selected_id = item_id
        self._restyle_rows()
        self._set_compare_active(False)
        self._request_preview()

    def _restyle_rows(self) -> None:
        for item in self._items:
            item["row"].configure(
                fg_color=(pair("seg_track")
                          if item["id"] == self._selected_id
                          else "transparent"))

    def _selected_item(self) -> dict | None:
        for item in self._items:
            if item["id"] == self._selected_id:
                return item
        return None

    def _remove(self, item_id) -> None:
        if self._running:
            return
        for i, item in enumerate(self._items):
            if item["id"] == item_id:
                item["row"].destroy()
                self._paths_seen.discard(item["path"])
                del self._items[i]
                if item_id == self._selected_id:
                    self._reset_preview()
                break
        if not self._items:
            self._empty.pack(pady=32, fill="x", expand=True)
        self._refresh_count()

    def _clear(self) -> None:
        if self._running:
            return
        for item in self._items:
            item["row"].destroy()
        self._items.clear()
        self._paths_seen.clear()
        self._reset_preview()
        self._empty.pack(pady=32, fill="x", expand=True)
        self._refresh_count()

    def _refresh_count(self) -> None:
        self._count_lbl.configure(text=tp("batch.count", len(self._items)))

    # ── Aperçu (thread dédiée, un calcul à la fois, cache LRU) ────────────
    def _request_preview(self) -> None:
        if self._pv_job is not None:
            self.after_cancel(self._pv_job)
        self._pv_job = self.after(_DEBOUNCE_MS, self._pump_preview)

    def _pump_preview(self) -> None:
        """Lance le calcul pour la sélection courante ; s'il y a déjà un
        calcul en vol, note le besoin (_pv_dirty) — il sera enchaîné à la
        fin du cours : jamais plus d'un vtracer d'aperçu actif."""
        self._pv_job = None
        if self._pv_busy:
            self._pv_dirty = True
            return
        item = self._selected_item()
        if item is None:
            self._preview.clear()
            self._pv_info.configure(text="")
            return
        params = self._params.get_params()
        invert = self._params.get_invert()
        key = (item["path"], tuple(sorted(params.items())), invert)
        cached = self._pv_cache.get(key)
        if cached is not None:
            self._pv_cache.move_to_end(key)
            self._show_preview(item, *cached)
            return

        snapshot = dict(
            key=key, path=item["path"],
            params=params, invert=invert,
            temp_dir=str(self.ctx.temp_dir),
        )
        self._pv_busy = True

        def work():
            try:
                with Image.open(snapshot["path"]) as img:
                    source = img.convert("RGBA")
                    source.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
                tmp_in = prepare_input(source, snapshot["temp_dir"],
                                       params.get("colormode", "color"),
                                       invert)
                svg = new_temp_path(snapshot["temp_dir"], ".svg")
                convert_file(tmp_in, svg, params)
                try:
                    os.remove(tmp_in)
                except OSError:
                    pass
                rendered = render_svg_to_pil(svg)
            except Exception as exc:
                self.after(0, lambda: self._pv_finished(snapshot, None, exc))
                return
            self.after(0, lambda: self._pv_finished(
                snapshot, (svg, rendered, source), None))

        threading.Thread(target=work, daemon=True,
                         name="ptp-preview-batch").start()

    def _pv_finished(self, snapshot: dict, result, exc: Exception | None) -> None:
        self._pv_busy = False
        if exc is None:
            self._pv_cache[snapshot["key"]] = result
            self._pv_cache.move_to_end(snapshot["key"])
            while len(self._pv_cache) > _CACHE_MAX:
                _key, evicted = self._pv_cache.popitem(last=False)
                self._discard_svg(evicted[0])
            item = self._selected_item()
            if snapshot["key"] == self._current_key():
                self._show_preview(item, *result)
        elif snapshot["key"] == self._current_key():
            self._preview.clear()
            self._pv_info.configure(text="")
            self.ctx.status.set_status(t("batch.pv_failed", err=exc), "error")
        if self._pv_dirty:
            self._pv_dirty = False
            self._pump_preview()

    def _current_key(self):
        """Clé de cache de la sélection courante, None si rien de sélectionné."""
        item = self._selected_item()
        if item is None:
            return None
        params = self._params.get_params()
        return (item["path"], tuple(sorted(params.items())),
                self._params.get_invert())

    def _show_preview(self, item: dict, svg_path: str, rendered, source) -> None:
        self._preview.set_svg(svg_path, (rendered.width, rendered.height),
                             original=source)
        kb = os.path.getsize(svg_path) / 1024
        kb_txt = f"{kb:.1f}" if kb < 10 else f"{kb:.0f}"
        self._pv_info.configure(
            text=t("batch.pv_info", name=os.path.basename(item["path"]),
                   kb=kb_txt))
        self._set_compare_active(False)

    @staticmethod
    def _discard_svg(svg_path: str) -> None:
        try:
            os.remove(svg_path)
        except OSError:
            pass

    def _reset_preview(self) -> None:
        """Sélection perdue : aperçu vide, état des boutons remis à zéro."""
        if self._pv_job is not None:
            self.after_cancel(self._pv_job)
            self._pv_job = None
        self._pv_dirty = False
        self._selected_id = None
        self._restyle_rows()
        self._set_compare_active(False)
        self._preview.clear()
        self._pv_info.configure(text="")

    # ── Comparaison ───────────────────────────────────────────────────────
    def _toggle_compare(self) -> None:
        self._set_compare_active(not self._preview.compare)

    def _set_compare_active(self, active: bool) -> None:
        self._compare_active = active
        self._preview.set_compare(active)
        self._style_compare_btn()

    def _style_compare_btn(self) -> None:
        if self._compare_active:
            self._btn_compare.configure(
                border_color=pair("primary"), text_color=pair("primary")
            )
        else:
            self._btn_compare.configure(
                border_color=pair("border"), text_color=pair("muted")
            )

    # ── Lancement / annulation ────────────────────────────────────────────
    def _launch(self) -> None:
        if self._running or not self._items:
            return
        params = self._params.get_params()
        params["invert"] = self._params.get_invert()
        if not self._out_dir:
            self.ctx.status.set_status(t("batch.pick_out_first"), "error")
            return
        try:
            os.makedirs(self._out_dir, exist_ok=True)
        except OSError as exc:
            self.ctx.status.set_status(t("batch.out_error", err=exc), "error")
            return

        worker = self._ensure_worker()
        worker.resume()
        self._running = True
        self._done = 0
        self._total = len(self._items)
        self._progress.set(0)
        self._progress_lbl.configure(text=f"0 / {self._total}")
        self._set_run_state(True)
        for item in self._items:
            out = next_output_path(self._out_dir,
                                   os.path.splitext(
                                       os.path.basename(item["path"]))[0])
            item["out"] = out
            item["status_lbl"].configure(text=t("batch.status.queued"))
            worker.submit(item["id"], item["path"], out, params)
        self.ctx.status.set_status(
            tp("batch.launching", self._total, dir=self._out_dir), "busy")

    def _cancel(self) -> None:
        if self.ctx.worker is not None:
            self.ctx.worker.cancel_all()
        self.ctx.status.set_status(t("batch.cancelling"), "busy")

    def _ensure_worker(self):
        if self.ctx.worker is None:
            self.ctx.worker = ConversionWorker()
        if not getattr(self, "_listening", False):
            self.ctx.worker.add_listener(self._queue_result)
            self._listening = True
        return self.ctx.worker

    def _set_run_state(self, running: bool) -> None:
        for btn in (self._btn_add_files, self._btn_add_dir, self._btn_clear,
                    self._btn_launch):
            btn.configure(state="disabled" if running else "normal")
        self._btn_cancel.configure(state="normal" if running else "disabled")
        for item in self._items:
            item["btn"].configure(
                state="disabled" if running else "normal")
        # La barre garde son état final : le reset se fait au lancement.

    # ── Résultats (thread worker → GUI) ───────────────────────────────────
    def _queue_result(self, item_id, status: str, detail: str) -> None:
        # Thread worker : re-dispatch sur le thread GUI (no-op CLI).
        try:
            self.after(0, lambda: self._apply_result(item_id, status, detail))
        except RuntimeError:
            pass  # application fermée pendant le lot

    def _apply_result(self, item_id, status: str, detail: str) -> None:
        if not self.winfo_exists():
            return
        for item in self._items:
            if item["id"] == item_id:
                break
        else:
            return  # item d'une autre vue (hot folder partage le worker)
        colors = {"done": pair("success"), "error": pair("error"),
                  "cancelled": pair("faint")}
        item["status"] = status  # CODE — libellé résolu à l'affichage
        item["status_lbl"].configure(
            text=t(f"batch.status.{status}"),
            text_color=colors.get(status, pair("faint")))
        if status == "done" and detail:
            # Miroir du survol d'erreur : le chemin exact passe dans la
            # barre d'état au survol de la ligne convertie.
            item["status_lbl"].bind(
                "<Enter>",
                lambda _e, d=detail:
                self.ctx.status.set_status(t("batch.saved_hover", path=d),
                                           "idle"),
            )
        elif status == "error" and detail:
            item["status_lbl"].bind(
                "<Enter>",
                lambda _e, d=detail:
                self.ctx.status.set_status(t("batch.error_hover", path=d),
                                           "error"),
            )
        self._done += 1
        self._progress.set(self._done / max(1, self._total))
        self._progress_lbl.configure(
            text=f"{self._done} / {self._total}")
        if self._done >= self._total:
            self._finish_run()

    def _finish_run(self) -> None:
        self._running = False
        self._set_run_state(False)
        errors = sum(1 for i in self._items if i["status"] == "error")
        cancelled = sum(1 for i in self._items if i["status"] == "cancelled")
        ok = len(self._items) - errors - cancelled
        dest = t("batch.dest_suffix", dir=self._out_dir) if self._out_dir else ""
        if errors:
            self.ctx.status.set_status(
                t("batch.finished_errors", ok=ok, errors=errors, dest=dest),
                "error")
        elif cancelled:
            self.ctx.status.set_status(
                t("batch.finished_cancelled", ok=ok, dest=dest), "idle")
        else:
            self.ctx.status.set_status(
                t("batch.finished_ok", ok=ok, dest=dest), "ok")

    # ── Divers ────────────────────────────────────────────────────────────
    def set_focus_mode(self, enabled: bool) -> None:
        # Focus : la carte de contrôles (destination, ajout) s'efface et la
        # liste s'étend ; l'aperçu et les réglages restent en place.
        if enabled:
            self._controls_card.grid_remove()
        else:
            self._controls_card.grid()

    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self._list.configure(fg_color=pair("surface"))
        self._restyle_rows()
        self._style_compare_btn()
        self._progress_lbl.configure(text_color=pair("faint"))
        self._dest_lbl.configure(text_color=pair("faint"))
        self._pv_info.configure(text_color=pair("muted"))
        for item in self._items:
            color = {"done": pair("success"), "error": pair("error"),
                     "cancelled": pair("faint")}.get(item["status"],
                                                     pair("faint"))
            item["status_lbl"].configure(text_color=color)
            item["name_lbl"].configure(text_color=pair("text"))
