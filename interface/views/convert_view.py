"""Vue Convertir — le flux complet image → SVG en trois temps numérotés.

01 · Source (dropzone) → 02 · Réglages (presets + paramètres) → 03 · SVG
(aperçu + téléchargement). La vue orchestre : les widgets sont muets, le
moteur est appelé via core/convert_service dans une thread daemon, jamais
sur le fil d'interface (garde `_gen` + debounce 600 ms, pattern v2).

Un bandeau promotionnel discret borde le bas (roulement DocuNest /
Cricut / LightBurn, un seul message à la fois) — retiré dès que la
licence est Pro.

Si convert/auto_detect est actif (vue Paramètres), une puce « Auto »
tête la rangée de presets : chaque image chargée est classée en thread
daemon (core/preset_detect) et le preset intégré correspondant est
appliqué — tout choix/édition manuelle décroche jusqu'au chargement
suivant. Pendant une conversion, l'aperçu montre un voile + spinner.
"""

import os
import shutil
import threading
import webbrowser
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core.constants import IMG_EXTS
from core.convert_service import (
    convert_file,
    new_temp_path,
    prepare_input,
    render_svg_to_pil,
)
from core.i18n import t
from core.preset_detect import detect_preset
from core.promos import strip_promos
from interface.theme.tokens import pair
from interface.views import View
from interface.widgets.card import Card, GhostButton, SectionHeader
from interface.widgets.dialogs import ManagePresetsDialog, SavePresetDialog
from interface.widgets.dropzone import Dropzone
from interface.widgets.params_panel import ParamsPanel
from interface.widgets.preset_picker import PresetPicker, custom_label
from interface.widgets.preview_canvas import PreviewCanvas
from interface.widgets.promo_strip import PromoStrip
from interface.widgets.scrollframe import ScrollFrame

_DEBOUNCE_MS = 600


def _filetypes():
    """Filtres du sélecteur — résolus à l'appel (jamais à l'import)."""
    return [
        (t("common.filetype_images"), "*.png *.jpg *.jpeg *.bmp *.webp"),
        (t("common.filetype_all"), "*.*"),
    ]


class ConvertView(View):
    def __init__(self, master, ctx):
        super().__init__(master, ctx)
        self._pil = None          # image source chargée
        self._input_name = ""
        self._svg_path = None     # dernier SVG généré (fichier temporaire)
        self._gen = 0             # garde anti-course entre conversions
        self._job = None          # timer de debounce
        self._compare_active = False
        self._auto_key = None     # verdict de détection pour l'image courante
        self._picker_auto = False # puce Auto présente au dernier refresh

        # « uniform » : split strict 40/60 — sinon les tailles demandées
        # (panneau de réglages, pied de l'aperçu) décalent la frontière et
        # l'aperçu rétrécit silencieusement d'un état à l'autre.
        self.grid_columnconfigure(0, weight=4, uniform="cols")
        self.grid_columnconfigure(1, weight=6, uniform="cols")
        self.grid_rowconfigure(1, weight=1)

        SectionHeader(self, t("convert.title")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        self._build_left()
        self._build_right()
        self._promo = None
        if not ctx.is_pro():
            self._build_promo()

        # Preset actif persisté ; réglages appliqués sans déclencher la
        # conversion (rien n'est encore chargé).
        self._presets = ctx.presets
        key = ctx.config.get("convert", "active_preset", "bw")
        if self._presets.params(key) is None:
            key = "bw"
        self._apply_preset(key, schedule=False)

    # ── Construction ──────────────────────────────────────────────────────
    def _build_left(self):
        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        self._left.grid_columnconfigure(0, weight=1)
        self._left.grid_rowconfigure(3, weight=1)

        self._source_header = SectionHeader(self._left, t("convert.src"))
        self._source_header.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._dropzone = Dropzone(
            self._left, on_activate=self._pick_file,
            on_drop=self._on_drop, on_remove=self._clear_image,
        )
        self._dropzone.grid(row=1, column=0, sticky="ew")

        SectionHeader(self._left, t("convert.settings")).grid(
            row=2, column=0, sticky="w", pady=(18, 8)
        )
        settings = Card(self._left)
        settings.grid(row=3, column=0, sticky="nsew")
        settings.grid_columnconfigure(0, weight=1)
        settings.grid_rowconfigure(2, weight=1)

        # Puces de presets + actions : « Enregistrer » ne s'active qu'en
        # état Personnalisé, « Gérer » ouvre renommage/suppression.
        picker_row = ctk.CTkFrame(settings, fg_color="transparent")
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

        ctk.CTkFrame(settings, height=1, corner_radius=0,
                     fg_color=pair("border")).grid(
            row=1, column=0, sticky="ew", padx=14
        )

        scroller = ScrollFrame(settings, fg_color="transparent")
        scroller.grid(row=2, column=0, sticky="nsew", padx=4, pady=(2, 6))
        # Poids sur la colonne du frame INTERNE (grid_columnconfigure n'est
        # pas surchargé par CTkScrollableFrame : l'appel atteint le frame
        # scrollé lui-même) — sans lui, ParamsPanel garde sa largeur
        # demandée au lieu de suivre celle de la carte.
        scroller.grid_columnconfigure(0, weight=1)
        self._params = ParamsPanel(scroller, on_change=self._on_params_change,
                                   on_expert=self._on_expert)
        self._params.grid(row=0, column=0, sticky="nsew", padx=8)
        # Préférence « Réglages avancés » restaurée avant toute interaction.
        self._params.set_expert(bool(
            self.ctx.config.get("convert", "expert_params", False)))

    def _build_right(self):
        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.grid(row=1, column=1, sticky="nsew")
        right = self._right
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        SectionHeader(right, t("convert.svg")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        card = Card(right)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._preview = PreviewCanvas(card)
        self._preview.grid(row=0, column=0, sticky="nsew", padx=16, pady=(14, 6))

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", padx=16, pady=(6, 14))
        self._info = ctk.CTkLabel(footer, text="", anchor="w",
                                  text_color=pair("muted"),
                                  font=ctk.CTkFont(size=11))
        self._info.pack(side="left", fill="x", expand=True)
        self._download_btn = ctk.CTkButton(
            footer, text=t("convert.download"), width=170, height=34,
            state="disabled", command=self._download,
        )
        self._download_btn.pack(side="right", padx=(10, 0))
        self._btn_1_1 = GhostButton(footer, text="1:1", width=52, height=34,
                                    command=self._preview.zoom_1_1)
        self._btn_1_1.pack(side="right", padx=(10, 0))
        self._btn_fit = GhostButton(footer, text=t("common.fit"), width=80,
                                    height=34, command=self._preview.fit)
        self._btn_fit.pack(side="right", padx=(10, 0))
        self._btn_compare = GhostButton(footer, text=t("common.compare"),
                                        width=90, height=34,
                                        command=self._toggle_compare)
        self._btn_compare.pack(side="right")

    # ── Promotion ─────────────────────────────────────────────────────────
    def _build_promo(self):
        # Une seule marque à la fois, roulement automatique, ordre de
        # départ aléatoire (strip_promos) ; piloté par la licence via
        # on_show : un utilisateur Pro ne voit aucune promotion.
        self._promo = PromoStrip(
            self, strip_promos(),
            on_open=lambda url: webbrowser.open(url),
        )
        self._promo.grid(row=2, column=0, columnspan=2, sticky="ew",
                         pady=(12, 0))

    def on_show(self):
        # Le toggle d'auto-détection a pu basculer dans Paramètres :
        # resynchroniser la rangée de puces (Auto apparue ou disparue).
        if self._auto_enabled() != self._picker_auto:
            self._sync_preset_state()
        # La licence peut avoir changé sur un autre écran (activation ou
        # expiration) : le bandeau suit, minuteur suspendu quand caché.
        if self.ctx.is_pro():
            if self._promo is not None:
                self._promo.stop()
                self._promo.destroy()
                self._promo = None
        elif self._promo is None:
            self._build_promo()
        else:
            self._promo.start()

    # ── Source ────────────────────────────────────────────────────────────
    def _pick_file(self):
        path = filedialog.askopenfilename(filetypes=_filetypes())
        if path:
            self._load_path(path)

    def _on_drop(self, paths):
        for p in paths:
            if str(p).lower().endswith(IMG_EXTS) and os.path.isfile(p):
                self._load_path(p)
                return
        self.ctx.status.set_status(t("convert.unsupported"), "error")

    def _load_path(self, path):
        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            self.ctx.status.set_status(t("convert.unreadable", err=exc),
                                       "error")
            return
        self._pil = img
        self._input_name = os.path.basename(path)
        self._dropzone.set_image(
            img, t("convert.src_info", name=self._input_name, w=img.width,
                   h=img.height)
        )
        self._info.configure(text="")
        self._download_btn.configure(state="disabled")
        self._set_compare_active(False)
        self._preview.clear()
        self.ctx.status.set_status(t("convert.loaded"), "idle")
        # Nouvelle image → le verdict précédent est périmé ; si l'auto est
        # active, la détection part en thread (elle arrive avant le debounce
        # 600 ms et `_apply_preset` remplace le timer : une seule conversion).
        self._auto_key = None
        if self._auto_enabled():
            self._detect_async(img)
        self._schedule()

    def _clear_image(self):
        """Suppression de la source : retour complet à l'état vide."""
        # La dropzone se réinitialise ici et pas seulement dans son bouton :
        # la vue reste juste si la suppression vient d'ailleurs (idempotent).
        self._dropzone.reset()
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self._gen += 1  # invalide un résultat de conversion en vol
        self._pil = None
        self._input_name = ""
        if self._svg_path and os.path.exists(self._svg_path):
            try:
                os.remove(self._svg_path)
            except OSError:
                pass
        self._svg_path = None
        self._auto_key = None
        self._preview.clear()
        self._info.configure(text="")
        self._download_btn.configure(state="disabled")
        self._set_compare_active(False)
        self.ctx.status.set_status(t("convert.removed"), "idle")

    # ── Réglages ──────────────────────────────────────────────────────────
    def _auto_enabled(self) -> bool:
        return bool(self.ctx.config.get("convert", "auto_detect", False))

    def _auto_label(self) -> str:
        # Résolu à l'appel : le libellé suit la langue courante.
        return t("presets.auto")

    def _preset_names(self) -> list[str]:
        names = [self._presets.display_name(k) for k in self._presets.keys()]
        if self._auto_enabled():
            names.insert(0, self._auto_label())
        return names

    def _refresh_picker(self, active_display: str | None) -> None:
        self._picker_auto = self._auto_enabled()
        self._picker.set_options(self._preset_names(),
                                 active=active_display)

    def _apply_preset(self, key: str, schedule: bool = True,
                      persist: bool = True):
        self._preset_key = key
        self._refresh_picker(self._presets.display_name(key))
        params = self._presets.params(key)
        params["invert"] = False
        self._params.set_params(params)
        self._btn_save_preset.configure(state="disabled")
        if schedule:
            # persist=False (application du verdict auto) : le dernier
            # preset manuellement choisi reste le preset actif persisté.
            if persist:
                self.ctx.config.set("convert", "active_preset", key)
            self._schedule()

    def _on_preset(self, label: str):
        if label == self._auto_label():
            # Puce Auto : ré-applique le dernier verdict de détection
            # (aucun si l'image chargée n'a pas encore été classée).
            if self._auto_key is not None:
                self._apply_preset(self._auto_key, persist=False)
                self._sync_preset_state()
            return
        key = self._presets.resolve(label)
        if key is not None:
            self._apply_preset(key)

    def _on_params_change(self, _key, _value):
        # Réglage manuel : le preset correspondant est recalculé — s'il n'y
        # en a plus, l'état devient « Personnalisé » et Enregistrer s'arme.
        self._sync_preset_state()
        self._schedule()

    def _sync_preset_state(self):
        """Puces + bouton Enregistrer d'après les réglages courants."""
        key = self._presets.matching(self._params.get_params())
        if (self._auto_key is not None and self._auto_enabled()
                and key == self._auto_key):
            # Réglages strictement ceux du preset détecté : puce Auto.
            # Toute édition manuelle dévie du matching et fait tomber ici.
            self._preset_key = key
            self._refresh_picker(self._auto_label())
            self._btn_save_preset.configure(state="disabled")
        elif key is None:
            self._preset_key = None
            # set_options et pas set_active : la puce d'un preset supprimé
            # dans « Gérer » doit disparaître immédiatement — l'état passe
            # à Personnalisé en conservant les réglages courants.
            self._refresh_picker(custom_label())
            self._btn_save_preset.configure(state="normal")
        else:
            self._preset_key = key
            self._refresh_picker(self._presets.display_name(key))
            self._btn_save_preset.configure(state="disabled")

    def _on_save_preset(self):
        if self._preset_key is not None:
            return
        SavePresetDialog(self, self.ctx, self._params.get_params(),
                         on_saved=self._on_preset_saved)

    def _on_preset_saved(self, name: str):
        # Les réglages courants SONT ceux du nouveau preset : pas de
        # re-conversion, juste l'état des puces.
        key = self._presets.resolve(name)
        self._preset_key = key
        self._refresh_picker(name)
        self._btn_save_preset.configure(state="disabled")
        self.ctx.config.set("convert", "active_preset", key)
        self.ctx.status.set_status(t("presets.saved", name=name), "ok")

    def _on_manage_presets(self):
        ManagePresetsDialog(self, self.ctx, on_changed=self._sync_preset_state)

    def _on_expert(self, enabled: bool) -> None:
        # Préférence de vue, persistée pour les deux vues (Convertir + Batch).
        self.ctx.config.set("convert", "expert_params", enabled)

    # ── Auto-détection du preset ──────────────────────────────────────────
    def _detect_async(self, img: Image.Image) -> None:
        """Classification en thread daemon — jamais sur le fil d'interface.

        `detect_preset` lit l'image via un convert() privé (tampon copié) :
        sûre face à la thread « ptp-convert » qui partage l'objet PIL.
        """
        def work():
            try:
                key = detect_preset(img)
            except Exception:
                return  # verdict manquant : le debounce déjà armé convertit
            self.after(0, lambda: self._on_detected(img, key))

        threading.Thread(target=work, daemon=True, name="ptp-detect").start()

    def _on_detected(self, img: Image.Image, key: str) -> None:
        # Garde par identité d'objet : image remplacée ou supprimée pendant
        # la détection → verdict périmé ; toggle coupé entre-temps aussi.
        if self._pil is not img or not self._auto_enabled():
            return
        self._auto_key = key
        self.ctx.status.set_status(
            t("convert.detected", name=self._presets.display_name(key)),
            "idle")
        self._apply_preset(key, persist=False)
        self._sync_preset_state()  # puce Auto (réglages == verdict)

    # ── Conversion ────────────────────────────────────────────────────────
    def _schedule(self):
        """Debounce : attendre la fin des frappes avant de lancer le moteur."""
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(_DEBOUNCE_MS, self._convert)

    def _convert(self):
        self._job = None
        if self._pil is None:
            return
        self._preview.set_busy(True)  # voile + spinner : conversion visible
        self._gen += 1
        gen = self._gen
        params = self._params.get_params()
        invert = self._params.get_invert()
        pil = self._pil
        temp_dir = str(self.ctx.temp_dir)
        self.ctx.status.set_status(t("convert.converting"), "busy")

        def work():
            try:
                tmp_in = prepare_input(pil, temp_dir,
                                       params.get("colormode", "color"), invert)
                svg = new_temp_path(temp_dir, ".svg")
                convert_file(tmp_in, svg, params)
                try:
                    os.remove(tmp_in)
                except OSError:
                    pass
                rendered = render_svg_to_pil(svg)
            except Exception as exc:
                self.after(0, lambda: self._on_error(gen, exc))
                return
            self.after(0, lambda: self._on_done(gen, svg, rendered))

        threading.Thread(target=work, daemon=True,
                         name="ptp-convert").start()

    def _on_error(self, gen: int, exc: Exception):
        if gen != self._gen:
            return
        self._preview.set_busy(False)  # résultat périmé : ne lève pas
        self.ctx.status.set_status(t("convert.failed", err=exc), "error")

    def _on_done(self, gen: int, svg_path: str, rendered):
        if gen != self._gen:
            os.remove(svg_path)  # résultat périmé : purge immédiate
            return
        self._preview.set_busy(False)
        if self._svg_path and os.path.exists(self._svg_path):
            try:
                os.remove(self._svg_path)
            except OSError:
                pass
        self._svg_path = svg_path

        # Aperçu interactif (zoom/pan/comparaison) — le canvas gère son
        # propre cache de rendu et son raffinement.
        self._preview.set_svg(svg_path, (rendered.width, rendered.height),
                             original=self._pil)

        kb = os.path.getsize(svg_path) / 1024
        kb_txt = f"{kb:.1f}" if kb < 10 else f"{kb:.0f}"
        self._info.configure(
            text=t("convert.info", w=rendered.width, h=rendered.height,
                   kb=kb_txt)
        )
        self._download_btn.configure(state="normal")
        self.ctx.status.set_status(t("convert.generated", kb=kb_txt), "ok")

    # ── Export ────────────────────────────────────────────────────────────
    def _download(self):
        if not self._svg_path or not os.path.exists(self._svg_path):
            return
        stem = os.path.splitext(self._input_name)[0] or "pixeltopath"
        out = filedialog.asksaveasfilename(
            defaultextension=".svg",
            initialfile=f"{stem}.svg",
            filetypes=[("SVG", "*.svg")],
        )
        if not out:
            return
        shutil.copyfile(self._svg_path, out)
        self.ctx.status.set_status(
            t("convert.saved_to", name=os.path.basename(out)), "ok"
        )

    # ── Comparaison ───────────────────────────────────────────────────────
    def _toggle_compare(self):
        self._set_compare_active(not self._preview.compare)

    def _set_compare_active(self, active: bool):
        self._compare_active = active
        self._preview.set_compare(active)
        self._style_compare_btn()

    def _style_compare_btn(self):
        # État actif = contour orange ; ré-appliqué après bascule de thème.
        if self._compare_active:
            self._btn_compare.configure(
                border_color=pair("primary"), text_color=pair("primary")
            )
        else:
            self._btn_compare.configure(
                border_color=pair("border"), text_color=pair("muted")
            )

    # ── Focus / thème ─────────────────────────────────────────────────────
    def apply_theme(self, tokens: dict) -> None:
        super().apply_theme(tokens)
        self._style_compare_btn()

    def set_focus_mode(self, enabled: bool) -> None:
        # Focus : seule la source s'efface — la zone Réglages reste (preset
        # + paramètres éditables face à l'aperçu) et l'aperçu s'élargit
        # (30/70 au lieu de 40/60, même groupe uniform).
        if enabled:
            self._source_header.grid_remove()
            self._dropzone.grid_remove()
            self.grid_columnconfigure(0, weight=3, uniform="cols")
            self.grid_columnconfigure(1, weight=7, uniform="cols")
        else:
            self._source_header.grid()
            self._dropzone.grid()
            self.grid_columnconfigure(0, weight=4, uniform="cols")
            self.grid_columnconfigure(1, weight=6, uniform="cols")
