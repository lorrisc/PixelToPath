"""Icône de barre système NATIVE Wayland/KDE — protocole StatusNotifierItem.

Le backend xorg de pystray parle XEmbed, le protocole X11 hérité : sous
Plasma Wayland il ne produit qu'une icône fantôme véhiculée par
xembedsniproxy (et une demande de permission de grabs d'entrée à
l'utilisateur — les menus XEmbed exigent XGrabPointer/XGrabKeyboard).
Ce module parle le protocole NATIF des bureaux modernes :
org.kde.StatusNotifierItem + com.canonical.dbusmenu sur le bus session,
via dbus-next (pur Python → s'empile dans PyInstaller sans dépendance
système). Fonctionne identiquement sur KDE/GNOME/Cinnamon, Wayland comme
X11 ; Plasma seule dépendance réelle (StatusNotifierWatcher, présent sur
toutes ces sessions).

Threading : identique à pystray (contrat de interface/tray.py). Une
boucle asyncio tourne sur SA thread daemon ; les appels DBus (clics)
n'y font qu'empiler dans la file `actions` — le thread Tk la pompe
(after) et exécute. Jamais d'appel Tk direct depuis DBus.

Cycle : show() lance la thread et attend ≤ 2 s l'enregistrement auprès
du watcher (le thread Tk ne doit pas rester bloqué). En cas d'échec
(pas de watcher : WM nus, wayfire…) show() renvoie False et l'appelant
applique son repli — jamais d'application introuvable.
"""

import asyncio
import inspect
import os
import queue
import sys
import threading

from dbus_next import Variant
from dbus_next.service import (ServiceInterface, method, dbus_property,
                               signal, PropertyAccess)

from core.constants import APP_NAME

_SNI_PATH = "/StatusNotifierItem"
_MENU_PATH = "/StatusNotifierMenu"
_WATCHER = "org.kde.StatusNotifierWatcher"
_WATCHER_PATH = "/StatusNotifierWatcher"

# Ids d'items dbusmenu (root 0) : ouvrir / séparateur / quitter.
_ID_OPEN, _ID_SEP, _ID_QUIT = 1, 2, 3

# Échec permanent mémorisé (pas de watcher) : les show() suivants ne
# re-testent pas et répondent immédiatement False.
_unavailable = False


def sni_available() -> bool:
    """Plausibilité synchronisée, sans I/O : Linux + un bus session
    trouvable. Le watcher réel est vérifié dans la thread (show)."""
    if sys.platform != "linux" or _unavailable:
        return False
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return True
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return bool(runtime) and os.path.exists(os.path.join(runtime, "bus"))


def _argb32(png_path: str) -> tuple:
    """PNG → (largeur, hauteur, pixels ARGB32 little-endian = BGRA).

    Format attendu par SNI (IconPixmap, a(iiay)) : A<<24|R<<16|G<<8|B,
    soit l'ordre octets B,G,R,A sur x86_64.
    """
    from PIL import Image

    im = Image.open(png_path).convert("RGBA")
    w, h = im.size
    rgba = im.tobytes()
    buf = bytearray(w * h * 4)
    buf[0::4] = rgba[2::4]  # B
    buf[1::4] = rgba[1::4]  # G
    buf[2::4] = rgba[0::4]  # R
    buf[3::4] = rgba[3::4]  # A
    return [w, h, bytes(buf)]


class _SniItem(ServiceInterface):
    """org.kde.StatusNotifierItem — l'icône elle-même (lecture seule)."""

    def __init__(self, tray: "SniTray"):
        self._tray = tray
        super().__init__("org.kde.StatusNotifierItem")

    # ── Propriétés (noms DBus en CamelCase, voulus) ──────────────────────
    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def Id(self) -> "s":
        return self._tray.title

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def Title(self) -> "s":
        return self._tray.title

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def Category(self) -> "s":
        return "ApplicationStatus"

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def Status(self) -> "s":
        return "Active"

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def WindowId(self) -> "u":
        return 0

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def IconName(self) -> "s":
        return "pixel-to-path"  # résolu via hicolor si l'app est installée

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def IconPixmap(self) -> "a(iiay)":
        return [self._tray.pixmap]

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def OverlayIconName(self) -> "s":
        return ""

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def OverlayIconPixmap(self) -> "a(iiay)":
        return []

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def AttentionIconName(self) -> "s":
        return ""

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def AttentionIconPixmap(self) -> "a(iiay)":
        return []

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def AttentionMovieName(self) -> "s":
        return ""

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def ToolTip(self) -> "(sa(iiay)ss)":
        return ["", [], self._tray.title, "PixelToPath"]

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def Menu(self) -> "o":
        return _MENU_PATH

    @dbus_property(PropertyAccess.READ)  # noqa: N802
    def ItemIsMenu(self) -> "b":
        return True

    # ── Méthodes ─────────────────────────────────────────────────────────
    @method()
    def Activate(self, x: "i", y: "i"):
        self._tray.actions.put("open")

    @method()
    def SecondaryActivate(self, x: "i", y: "i"):
        self._tray.actions.put("open")

    @method()
    def ContextMenu(self, x: "i", y: "i"):
        pass  # Plasma ouvre lui-même le dbusmenu (Menu + ItemIsMenu)

    @method()
    def Scroll(self, dx: "i", dy: "i", orientation: "s"):
        pass


class _DBusMenu(ServiceInterface):
    """com.canonical.dbusmenu — le menu contextuel de l'icône.

    Arbre statique minimal : root(0) → Ouvrir(1), séparateur(2),
    Quitter(3). rebuild() émet LayoutUpdated pour que Plasma re-tire
    les libellés traduits.
    """

    def __init__(self, tray: "SniTray"):
        self._tray = tray
        super().__init__("com.canonical.dbusmenu")

    # ── aide : propriétés d'un item ──────────────────────────────────────
    def _props(self, item_id: int) -> dict:
        if item_id == _ID_SEP:
            return {"type": _sv("s", "separator"), "visible": _sv("b", True)}
        label = (self._tray.label_open if item_id == _ID_OPEN
                 else self._tray.label_quit)
        return {"label": _sv("s", label), "enabled": _sv("b", True),
                "visible": _sv("b", True), "icon-name": _sv("s", "")}

    def _children(self, parent: int) -> list:
        if parent != 0:
            return []
        return [_mkitem(_ID_OPEN, self._props(_ID_OPEN)),
                _mkitem(_ID_SEP, self._props(_ID_SEP)),
                _mkitem(_ID_QUIT, self._props(_ID_QUIT))]

    # ── API dbusmenu ─────────────────────────────────────────────────────
    @method()
    def GetLayout(self, parent_id: "i", recursion_depth: "i",
                  property_names: "as") -> "u(ia{sv}av)":
        props = ({"children-display": _sv("s", "submenu"),
                  "visible": _sv("b", True)} if parent_id == 0 else
                 self._props(parent_id))
        return [self._tray.revision,
                [parent_id, props, self._children(parent_id)]]

    @method()
    def GetGroupProperties(self, ids: "ai",
                           property_names: "as") -> "a(ia{sv})":
        wanted = ids or [_ID_OPEN, _ID_SEP, _ID_QUIT]
        return [[i, self._props(i)] for i in wanted if i != 0]

    @method()
    def AboutToShow(self, item_id: "i") -> "b":
        return False

    @method()
    def Event(self, item_id: "i", event_id: "s", data: "v", timestamp: "u"):
        if event_id != "clicked":
            return
        if item_id == _ID_OPEN:
            self._tray.actions.put("open")
        elif item_id == _ID_QUIT:
            self._tray.actions.put("quit")

    @signal()
    def LayoutUpdated(self) -> "ui":
        return [self._tray.revision, 0]


# ── helpers de sérialisation (hors classes : lisibles) ─────────────────
def _sv(sig: str, value):
    """Propriété dbusmenu typée (a{sv} exige des Variant)."""
    from dbus_next import Variant

    return Variant(sig, value)


def _mkitem(item_id: int, props: dict):
    """Enfant de layout : Variant sur (id, props, enfants)."""
    from dbus_next import Variant

    return Variant("(ia{sv}av)", [item_id, props, []])


class SniTray:
    """Façade threadée — même contrat que l'icône pystray de tray.py."""

    def __init__(self, actions: queue.Queue):
        self.actions = actions  # file partagée avec TrayController
        self.title = APP_NAME
        self.label_open = "Open"
        self.label_quit = "Quit"
        self.pixmap = (0, 0, b"")
        self.revision = 1

        self._thread = None
        self._loop = None
        self._stop_evt = None      # asyncio.Event (thread DBus)
        self._registered = False
        self._ready = threading.Event()

    # ── cycle de vie ─────────────────────────────────────────────────────
    def show(self, title: str, label_open: str, label_quit: str,
             icon_path: str) -> bool:
        """Enregistre l'item (idempotent). True si vivant côté watcher."""
        if self._thread is not None:
            return self._registered
        self.title, self.label_open, self.label_quit = (
            title, label_open, label_quit)
        try:
            self.pixmap = _argb32(icon_path)
        except Exception:
            self.pixmap = (0, 0, b"")  # IconName seul alors
        self._thread = threading.Thread(
            target=self._run, name="ptp-tray-sni", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)  # le thread Tk ne doit pas rester bloqué
        return self._registered

    def rebuild(self, title: str, label_open: str, label_quit: str) -> None:
        """Langue changée : ré-émet la layout, Plasma re-tire les labels."""
        self.title, self.label_open, self.label_quit = (
            title, label_open, label_quit)
        self.revision += 1
        if self._loop is not None and self._registered:
            self._loop.call_soon_threadsafe(self._emit_layout)

    def stop(self) -> None:
        if self._loop is not None and self._stop_evt is not None:
            self._loop.call_soon_threadsafe(self._stop_evt.set)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._loop = None
        self._registered = False

    # ── thread DBus ──────────────────────────────────────────────────────
    def _emit_layout(self):
        for iface in _DBusMenu._instances:  # rempli à l'export
            iface.LayoutUpdated()

    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception:
            global _unavailable
            _unavailable = True  # re-test inutile dans ce process
        finally:
            self._ready.set()

    async def _main(self):
        from dbus_next.aio.message_bus import MessageBus

        bus = await MessageBus().connect()
        intro = await bus.introspect(_WATCHER, _WATCHER_PATH)
        wobj = bus.get_proxy_object(_WATCHER, _WATCHER_PATH, intro)
        watcher = wobj.get_interface(_WATCHER)

        item = _SniItem(self)
        menu = _DBusMenu(self)
        _DBusMenu._instances = [menu]
        bus.export(_SNI_PATH, item)
        bus.export(_MENU_PATH, menu)

        # Nom conventionnel (best-effort) : le watcher identifie aussi
        # très bien l'item par notre nom unique de bus.
        try:
            await bus.request_name(
                f"org.kde.StatusNotifierItem-{os.getpid()}-1")
        except Exception:
            pass

        # Sans ça pas d'icône : le watcher ne liste que ce qu'on lui
        # déclare explicitement.
        await watcher.call_register_status_notifier_item(_SNI_PATH)

        self._loop = asyncio.get_running_loop()
        self._stop_evt = asyncio.Event()
        self._registered = True
        self._ready.set()
        await self._stop_evt.wait()

        # Arrêt : déclaration obsolète chez le watcher, puis bus.
        try:
            await watcher.call_unregister_status_notifier_item(_SNI_PATH)
        except Exception:
            pass  # certains watchers n'ont pas Unregister : disparition
        disc = bus.disconnect()
        if inspect.isawaitable(disc):
            await disc
