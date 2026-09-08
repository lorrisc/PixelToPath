"""Icône de barre système — best-effort, jamais piégeante.

Ordre des backends dans show() :
1. SNI natif (interface/tray_sni.py) — le protocole des bureaux modernes
   (KDE/GNOME/Cinnamon, Wayland comme X11). Toujours tenté en premier.
2. pystray — backend xorg XEmbed, UNIQUEMENT hors Wayland : sous
   Plasma Wayland ce pont hérité (xembedsniproxy) ne donne qu'une icône
   fantôme ET une demande de permission de grabs d'entrée (les menus
   XEmbed exigent XGrabPointer/XGrabKeyboard) — pire que pas d'icône.
   pystray choisit son backend par imports conditionnels invisibles à
   l'analyse statique de PyInstaller — d'où les hiddenimports des specs.

Tout échec est non bloquant : show() renvoie False et l'appelant
iconifie la fenêtre au lieu de la masquer (ou quitte réellement à la
fermeture) — jamais de fenêtre introuvable.

Threading : les callbacks pystray/dbus arrivent sur LEUR thread — ils
ne font qu'empiler une action dans `actions` ; le thread Tk la pompe
(after) et exécute. Jamais d'appel Tk direct depuis eux.
"""

import os
import queue
import subprocess

from PIL import Image

from core.constants import APP_NAME
from core.i18n import t
from interface.utils import resource_path

_ICON = "interface/assets/app_icon.png"
# Même design, dérivé de l'asset 180 px de la marque : plus de détails
# une fois réduit à la taille réelle du tray (~24 px).
_ICON_HI = "interface/assets/app_icon_128.png"


def _best_icon() -> str:
    """La plus haute résolution disponible (repli : icône 64 px)."""
    hi = resource_path(_ICON_HI)
    return hi if os.path.exists(hi) else resource_path(_ICON)


def _on_wayland() -> bool:
    return (bool(os.environ.get("WAYLAND_DISPLAY"))
            or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland")


class TrayController:
    def __init__(self):
        # Actions demandées depuis les threads pystray/dbus ("open" |
        # "quit"), consommées par l'App sur le thread Tk.
        self.actions: queue.Queue = queue.Queue()
        self._icon = None
        self._sni = None

    def available(self) -> bool:
        try:
            from interface import tray_sni
            if tray_sni.sni_available():
                return True
        except Exception:
            pass
        try:
            import pystray  # noqa: F401
            return True
        except Exception:
            return False

    def _build_menu(self, pystray):
        """Menu (re)construit dans la langue courante ; les lambdas pystray
        vivent sur SA thread — elles n'empilent que dans la file partagée."""
        return pystray.Menu(
            # default : action du double-clic (Windows).
            pystray.MenuItem(
                t("app.tray_open", app=APP_NAME),
                lambda *_: self.actions.put("open"), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("app.tray_quit"),
                             lambda *_: self.actions.put("quit")),
        )

    def show(self) -> bool:
        """Crée et lance l'icône (idempotent). True si elle est vivante."""
        if self._icon is not None or self._sni is not None:
            return True

        # 1. SNI natif : KDE/GNOME/Cinnamon, Wayland comme X11.
        try:
            from interface import tray_sni
        except Exception:  # dbus_next absent du bundle : repli pystray
            tray_sni = None
        if tray_sni is not None and tray_sni.sni_available():
            sni = tray_sni.SniTray(self.actions)
            if sni.show(title=APP_NAME,
                        label_open=t("app.tray_open", app=APP_NAME),
                        label_quit=t("app.tray_quit"),
                        icon_path=_best_icon()):
                self._sni = sni
                return True
            self._sni = None  # pas de watcher : repli ci-dessous

        # 2. pystray xorg (XEmbed) : X11 uniquement — interdit sous
        #    Wayland (icône fantôme + permission de grabs d'entrée).
        if _on_wayland():
            return False
        try:
            import pystray

            image = Image.open(resource_path(_ICON))
            menu = self._build_menu(pystray)
            icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
            icon.run_detached()
            self._icon = icon
            return True
        except Exception as exc:
            print(t("app.tray_error", err=exc))
            return False

    def rebuild_menu(self) -> None:
        """Langue changée : remplace le menu si l'icône vit (best-effort).

        Sans icône, le prochain show() construira dans la nouvelle langue.
        """
        if self._sni is not None:
            try:
                self._sni.rebuild(title=APP_NAME,
                                  label_open=t("app.tray_open", app=APP_NAME),
                                  label_quit=t("app.tray_quit"))
            except Exception:
                pass  # backend capricieux : jamais bloquant
        if self._icon is None:
            return
        try:
            import pystray

            self._icon.menu = self._build_menu(pystray)
            self._icon.update_menu()
        except Exception:
            pass  # backend capricieux : jamais bloquant

    def stop(self) -> None:
        if self._sni is not None:
            try:
                self._sni.stop()
            except Exception:
                pass
            self._sni = None
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def notify(self, message: str, title: str = APP_NAME) -> bool:
        """Notification best-effort : bulle pystray, sinon notify-send."""
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
                return True
            except Exception:
                pass  # backend sans notifications → repli ci-dessous
        try:
            subprocess.Popen(
                ["notify-send", "-t", "5000", title, message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False  # silencieux : rien de disponible
