"""Icône de barre système (pystray) — best-effort, jamais piégeante.

pystray choisit son backend par imports conditionnels (appindicator,
ayatana, xorg…) invisibles à l'analyse statique de PyInstaller — d'où
les hiddenimports des specs GUI. Sous Wayland sans appindicator, le
backend xorg requiert python-xlib et un pont XEmbed (xembedsniproxy
sous Plasma). Tout échec est non bloquant : show() renvoie False et
l'appelant iconifie la fenêtre au lieu de la masquer — jamais de
fenêtre introuvable.

Threading : les callbacks pystray arrivent sur SA thread — ils ne font
qu'empiler une action dans `actions` ; le thread Tk la pompe (after)
et exécute. Jamais d'appel Tk direct depuis pystray.
"""

import queue
import subprocess

from PIL import Image

from core.constants import APP_NAME
from core.i18n import t
from interface.utils import resource_path

_ICON = "interface/assets/app_icon.png"


class TrayController:
    def __init__(self):
        # Actions demandées depuis la thread pystray ("open" | "quit"),
        # consommées par l'App sur le thread Tk.
        self.actions: queue.Queue = queue.Queue()
        self._icon = None

    def available(self) -> bool:
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
        if self._icon is not None:
            return True
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
        if self._icon is None:
            return
        try:
            import pystray

            self._icon.menu = self._build_menu(pystray)
            self._icon.update_menu()
        except Exception:
            pass  # backend capricieux : jamais bloquant

    def stop(self) -> None:
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
