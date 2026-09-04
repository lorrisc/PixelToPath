"""PixelToPath — shell de l'application (v3).

Le shell ne fait qu'assembler : config → thème → rail de navigation +
conteneur de vues + barre d'état. Toute la logique vit dans core/ (sans
GUI) et les vues orchestrent des widgets muets.
"""

import argparse
import os
import queue
import tempfile

import customtkinter as ctk
import tkinter as tk
from tkinterdnd2 import TkinterDnD

from core.config import ConfigStore
from core.constants import APP_NAME
from core.convert_service import ConversionWorker
from core.hotfolders import HotFolderManager
from core.history import HotFolderHistory
from core import i18n
from core.i18n import t, tp
from core.licensing import LicenseManager
from core.presets import PresetController
from interface.context import AppContext
from interface.theme.tokens import DARK, LIGHT, ThemeService, pair
from interface.tray import TrayController
from interface.utils import resource_path
from interface.widgets import NavRail, StatusBar
from interface.widgets.dialogs import UpgradeDialog
from interface.views import (
    BatchView,
    ConvertView,
    HotFolderView,
    LockedView,
    PartnersView,
    SettingsView,
)

# Vues réservées à la licence Pro → LockedView tant que pas de clé active.
# Titre = clé i18n, résolu à la construction de la vue (t).
PRO_VIEWS = {
    "batch": ("nav.batch", BatchView),
    "hotfolder": ("nav.hotfolder", HotFolderView),
}


class App(TkinterDnD.Tk):
    """Fenêtre principale : rail + conteneur de vues + barre d'état."""

    def __init__(self, ctx: AppContext, start_minimized: bool = False):
        super().__init__()
        self.ctx = ctx
        self.title(APP_NAME)

        self._start_minimized = start_minimized
        self._geometry_placed = False
        self._hidden = False
        self._hidden_done = 0
        self._notify_job = None
        self.tray = TrayController()
        # Notifications coalescées : listener sur le worker partagé — créé
        # avant ou après l'App selon l'ordre de main() (add_listener
        # dédoublonne les bound methods égales).
        if ctx.worker is not None:
            ctx.worker.add_listener(self._on_worker_result)

        # KWin/Wayland ignore les hints de géométrie pré-mapping et écrase
        # une première demande trop précoce (placement maison, hauteur
        # bridée) : redemander tant que la taille demandée n'est pas effective.
        self.minsize(1100, 720)
        self.after(150, self._place_window)
        if start_minimized:
            # Retirée avant le premier mapping : aucun flash au démarrage.
            self.withdraw()

    def _place_window(self, tries: int = 8) -> None:
        if not self._start_minimized:
            self._apply_window_placement(tries)
        # Démarrage masqué : pas de course de géométrie (les hints
        # pré-mapping ne concernent pas une fenêtre non mappée) — le
        # placement aura lieu à la première restauration.

        # Dossier temporaire partagé (aperçus, préparations d'images).
        self.ctx.temp_dir = (
            os.path.join(tempfile.gettempdir(), "PixelToPath")
        )
        os.makedirs(self.ctx.temp_dir, exist_ok=True)

        self._focus_mode = False
        self._current = None
        self._views: dict[str, object | None] = {
            key: None for key in ("convert", "batch", "hotfolder",
                                  "partners", "settings")
        }

        # Racine = TkinterDnD.Tk (pas ctk.CTk) : sans ça, le gris Tk par
        # défaut (#d9d9d9) transparaît à travers tous les frames transparents.
        self.configure(bg=ThemeService.color("bg"))
        self._build_interface()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Escape>", self._on_escape)

        # Course customtkinter : la rafale de Configure du passage maximisé
        # peut perdre le dessin du texte de quelques CTkLabel (item créé
        # puis effacé — libellé blanc jusqu'au prochain événement). Re-poser
        # les textes une fois la géométrie stabilisée force le redessin.
        self.after(1600, self._settle_label_texts)

        # Actions de l'icône système : empilées par la thread pystray,
        # exécutées ici (thread Tk) via un pompage périodique.
        self.after(100, self._pump_tray)
        self._geometry_placed = not self._start_minimized
        if self._start_minimized:
            self._show_tray_background()
        # Surveillance : après le build (la barre d'état existe), au
        # premier tour de mainloop.
        self.after(0, self.start_hotfolders)

    def _apply_window_placement(self, tries: int = 8) -> None:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        # Maximisé = 100 % de l'écran (zone utile), positionné par le WM :
        # le seul moyen fiable X11/Wayland/Windows — une géométrie forcée
        # serait rognée par les décorations côté serveur. Ne JAMAIS
        # retourner tôt : la suite de l'initialisation suit, quel que
        # soit le chemin pris par l'état de fenêtre.
        zoomed = False
        try:
            self.state("zoomed")
            if self.state() == "iconic":  # course pré-mapping (KWin/XWayland)
                self.deiconify()
                self.state("zoomed")
            zoomed = self.state() == "zoomed"
        except tk.TclError:
            pass

        if not zoomed:
            # Repli : certains WM ignorent l'état pré-mapping → géométrie
            # plein écran + re-demande tant que la taille n'est pas effective.
            target = f"{screen_w}x{screen_h}+0+0"
            self.geometry(target)

            def _check(remaining: int):
                # KWin ajoute la barre de titre au y → ne comparer que WxH.
                if (self.winfo_geometry().split("+")[0] != target.split("+")[0]
                        and remaining):
                    self.geometry(target)
                    self.after(150, lambda: _check(remaining - 1))

            self.after(150, lambda: _check(tries))
        self._geometry_placed = True

    # ── Barre système ─────────────────────────────────────────────────────
    def _show_tray_background(self) -> None:
        """Icône système pour un démarrage masqué ; en cas d'échec la
        fenêtre est iconifiée (barre des tâches) — jamais introuvable."""
        self._hidden = True
        if not self.tray.show():
            self.iconify()
            self._hidden = False

    def _hide_to_tray(self) -> None:
        self.withdraw()
        self._hidden = True
        if self.tray.show():
            self.tray.notify(t("app.hidden_notify"))
        else:
            self.iconify()
            self._hidden = False
        self.ctx.status.set_status(
            t("app.hidden_status") if self._hidden
            else t("app.tray_unavailable"), "idle")

    def _restore(self) -> None:
        self._hidden = False
        self.deiconify()
        if not self._geometry_placed:  # démarrage masqué : jamais placée
            self._apply_window_placement()
        self.lift()
        self.focus_force()

    def _pump_tray(self) -> None:
        """Exécute sur le thread Tk les actions demandées par pystray."""
        try:
            while True:
                action = self.tray.actions.get_nowait()
                if action == "open":
                    self._restore()
                elif action == "quit":
                    self._really_quit()
        except queue.Empty:
            pass
        self.after(100, self._pump_tray)

    # ── Notifications coalescées ─────────────────────────────────────────
    def _on_worker_result(self, item_id, status: str, detail: str) -> None:
        # Thread worker : conversion hot folder réussie pendant que la
        # fenêtre est masquée → UNE notification par salve, pas une par
        # fichier (une copie de dossier déclencherait une pluie de bulles).
        if not (isinstance(item_id, tuple) and item_id
                and item_id[0] == "hotfolder") or status != "done":
            return
        try:
            self.after(0, self._count_hidden_conversion)
        except RuntimeError:
            pass  # application fermée pendant une conversion

    def _count_hidden_conversion(self) -> None:
        if not self._hidden:
            return
        self._hidden_done += 1
        if self._notify_job is None:
            self._notify_job = self.after(
                1500, self._flush_hidden_notifications)

    def _flush_hidden_notifications(self) -> None:
        self._notify_job = None
        count, self._hidden_done = self._hidden_done, 0
        if count:
            self.tray.notify(tp("app.hidden_done", count))

    def start_hotfolders(self) -> int:
        """Lance les surveillances activées dès l'ouverture de l'app, sans
        attendre la construction de la vue Hot folder (Pro requis)."""
        if not self.ctx.is_pro() or self.ctx.hotfolders is None:
            return 0
        started = self.ctx.hotfolders.start_all()
        if started:
            if self._hidden:
                self.tray.notify(tp("app.watching_hidden", started))
            elif self.ctx.status is not None:
                self.ctx.status.set_status(
                    tp("app.hotfolder_active", started), "ok")
        return started

    def _settle_label_texts(self, widget=None) -> None:
        """Re-pose le texte de chaque CTkLabel pour forcer son redessin."""
        widget = widget or self
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                txt = child.cget("text")
                if txt:
                    child.configure(text=txt)
            self._settle_label_texts(child)

    # ── Interface ────────────────────────────────────────────────────────
    def _build_interface(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._nav = NavRail(
            self,
            on_select=self.show_view,
            on_pro_status=self._on_pro_status,
        )
        self._nav.grid(row=0, column=0, sticky="ns")
        self._nav.select("convert")
        self._nav.set_pro(self.ctx.is_pro())

        self._content = ctk.CTkFrame(self, fg_color=pair("bg"))
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._status = StatusBar(self, on_focus_toggle=self.toggle_focus_mode)
        self._status.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.ctx.status = self._status  # les vues publient leur état via ctx

        self.show_view("convert")

    def show_view(self, key: str) -> None:
        """Bascule vers la vue `key` (instanciée paresseusement, jamais détruite)."""
        view = self._views.get(key)
        if view is None:
            view = self._build_view(key)
            self._views[key] = view
            view.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        for other_key, other in self._views.items():
            if other is not None and other_key != key:
                other.grid_remove()
        view.grid()
        # Une vue cachée pendant une bascule de thème peut rester avec un
        # canvas interne non repeint : ré-habiller toute la sous-arborescence.
        ThemeService.apply_all(view)
        view.set_focus_mode(self._focus_mode)
        view.on_show()  # resynchronisation (presets, surveillance… changés ailleurs)
        self._nav.select(key)
        self._current = key

    def _build_view(self, key: str):
        if key == "convert":
            return ConvertView(self._content, self.ctx)
        if key == "partners":
            return PartnersView(self._content, self.ctx)
        if key == "settings":
            return SettingsView(
                self._content, self.ctx,
                on_language_change=self.rebuild_for_language,
                on_theme_change=self.set_theme,
                on_pro_change=self._refresh_pro_state,
            )
        if key in PRO_VIEWS:
            feature_key, view_cls = PRO_VIEWS[key]
            if self.ctx.is_pro():
                return view_cls(self._content, self.ctx)
            return LockedView(
                self._content, self.ctx, feature=t(feature_key),
                on_upgrade=self._on_pro_status,
            )
        raise KeyError(key)

    # ── Langue ───────────────────────────────────────────────────────────
    def rebuild_for_language(self):
        """Langue changée (vue Paramètres) : les vues — orchestratrices
        sans état, tout vit en config — sont détruites puis recréées dans
        la nouvelle langue ; le rail, la barre d'état et le menu du tray
        sont re-traduits en place. Les vues Pro verrouillées le restent :
        show_view repasse par _build_view et son test is_pro()."""
        keep = self._current or "convert"
        # Dialogues ouverts au niveau du shell (rail) : détruits, les
        # dialogues posés par une vue meurent avec elle.
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                child.destroy()
        for view in self._views.values():
            if view is not None:
                view.destroy()
        self._views = {key: None for key in self._views}
        self._nav.retranslate()
        self._status.retranslate()
        self.tray.rebuild_menu()
        self.show_view(keep)  # reconstruit + re-habille + resynchronise

    # ── Thème / focus / licence ─────────────────────────────────────────
    def set_theme(self, mode: str):
        """Depuis la vue Paramètres : bascule le thème, no-op si le mode
        demandé est déjà actif."""
        if mode == ThemeService.mode().lower():
            return
        # Fond de la racine mis à jour AVANT la bascule : les frames
        # transparents relisent la couleur du master pendant la
        # re-résolution déclenchée par set_appearance_mode().
        self.configure(bg=(LIGHT if ThemeService.is_dark() else DARK)["bg"])
        ThemeService.toggle(self)
        self.ctx.config.set(
            "appearance", "mode", ThemeService.mode().lower()
        )

    def toggle_focus_mode(self):
        self._focus_mode = not self._focus_mode
        if self._focus_mode:
            self._nav.grid_remove()
        else:
            self._nav.grid()
        self._status.set_focus_active(self._focus_mode)
        if self._current is not None and self._views[self._current]:
            self._views[self._current].set_focus_mode(self._focus_mode)

    def _on_escape(self, _event=None):
        if self._focus_mode:
            self.toggle_focus_mode()

    def _on_pro_status(self):
        """Clic sur le statut Pro / CTA d'une vue verrouillée."""
        if self.ctx.is_pro():
            self._status.set_status(t("app.pro_active"), "ok")
        else:
            UpgradeDialog(self, self.ctx, on_changed=self._refresh_pro_state)

    def _refresh_pro_state(self):
        """Après activation/désactivation : rail + vue Pro courante reconstruite."""
        pro = self.ctx.is_pro()
        self._nav.set_pro(pro)
        # La surveillance suit la licence : perte → arrêt (les entrées
        # gardent enabled=True, la réactivation suffit à reprendre) ;
        # gain → reprise des dossiers activés.
        if self.ctx.hotfolders is not None:
            if pro:
                self.ctx.hotfolders.start_all()
            else:
                self.ctx.hotfolders.stop_all(persist=False)
        # Le bandeau promo de l'accueil suit la licence : invisible sitôt
        # Pro, reconstruit au retour en gratuit (no-op si jamais affichée).
        convert = self._views.get("convert")
        if convert is not None:
            convert.on_show()
        key = self._current
        if key in PRO_VIEWS:
            # La vue verrouillée est remplacée par la vraie (ou l'inverse) :
            # jamais construite en double, l'ancienne est détruite.
            old = self._views.get(key)
            if old is not None:
                old.destroy()
            self._views[key] = None
            self.show_view(key)
        self._status.set_status(
            t("app.pro_active") if pro else t("app.free_mode"),
            "ok" if pro else "idle",
        )

    # ── Fermeture ────────────────────────────────────────────────────────
    def on_close(self):
        # Au moins une surveillance active : la fenêtre se masque, tout
        # continue en arrière-plan via l'icône système.
        if self.ctx.hotfolders is not None and self.ctx.hotfolders.any_running():
            self._hide_to_tray()
            return
        self._really_quit()

    def _really_quit(self):
        # Chemin de sortie unique (croix sans surveillance, « Quitter » de
        # l'icône système) : rien ne survit — watchers, worker et tray sont
        # arrêtés, les threads sont daemoniques.
        if self.ctx.hotfolders is not None:
            self.ctx.hotfolders.stop_all(persist=False)

        # 1. Arrêter le worker AVANT de toucher au dossier temporaire.
        if self.ctx.worker is not None:
            try:
                self.ctx.worker.shutdown()
            except Exception as exc:  # ne jamais bloquer la fermeture
                print(t("app.worker_stop", err=exc))

        # 2. Nettoyer les fichiers temporaires.
        temp_dir = self.ctx.temp_dir
        if temp_dir and os.path.isdir(temp_dir):
            for name in os.listdir(temp_dir):
                path = os.path.join(temp_dir, name)
                try:
                    os.remove(path)
                except OSError as exc:
                    print(t("app.cleanup_error", path=path, err=exc))
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass  # non vide (fichiers verrouillés) — le système purgera

        # 3. Icône système (join de sa thread), puis la fenêtre.
        self.tray.stop()
        self.destroy()


def get_scale():
    root = tk.Tk()
    dpi = root.winfo_fpixels("1i")
    root.destroy()
    return dpi / 96


def main():
    scale = get_scale()
    ctk.set_widget_scaling(scale)
    ctk.set_window_scaling(scale)

    # Thème avant toute création de widget : le json en paires [light, dark]
    # habille les widgets ctk, ThemeService porte le mode courant.
    ctk.set_default_color_theme(resource_path("interface/theme/pixeltopath.json"))

    config = ConfigStore()
    # Langue avant tout texte : argparse fige son aide à la construction.
    i18n.install_from_config(config)
    parser = argparse.ArgumentParser(prog=APP_NAME, description=t("app.tagline"))
    parser.add_argument(
        "--minimized", action="store_true",
        help=t("app.minimized_help"))
    args = parser.parse_args()

    license_manager = LicenseManager(config)
    presets = PresetController(config)
    ctx = AppContext(config=config, temp_dir=None,
                     presets=presets, license=license_manager)

    # Le worker partagé (batch + hot folder) naît au premier besoin du
    # manager ; l'App y attache alors son listener de notifications.
    holder: dict = {}

    def worker_factory():
        worker = ConversionWorker()
        ctx.worker = worker
        app = holder.get("app")
        if app is not None:
            worker.add_listener(app._on_worker_result)
        return worker

    # La surveillance vit au niveau de l'application : démarrage avant
    # toute vue, survit au masquage de la fenêtre.
    ctx.hotfolders = HotFolderManager(
        config, presets, worker_factory=worker_factory,
        history=HotFolderHistory())

    ThemeService.set_mode(ctx.config.get("appearance", "mode", "light").capitalize())

    app = App(ctx, start_minimized=args.minimized)
    holder["app"] = app
    # La fenêtre existe : les réponses réseau peuvent revenir au thread GUI
    # et la revalidation hebdomadaire démarre.
    license_manager.set_scheduler(app.after)
    license_manager.start_periodic_validation()

    icon = tk.PhotoImage(file=resource_path("interface/assets/app_icon.png"))
    app.iconphoto(True, icon)
    app._icon = icon  # garde une référence (sinon garbage-collecté)

    app.mainloop()


if __name__ == "__main__":
    main()
