r"""Lancement automatique à l'ouverture de session — sans dépendance GUI.

Windows : valeur « PixelToPath » dans HKCU\Software\Microsoft\Windows\
CurrentVersion\Run. Linux : entrée XDG Autostart
($XDG_CONFIG_HOME/autostart/PixelToPath.desktop — distinct du dossier
de config de l'app). macOS : stub — LaunchAgents à écrire le jour où
l'app y est distribuée.

L'artefact OS fait foi pour l'état activé/désactivé (l'utilisateur peut
éditer le registre ou le .desktop à la main) : autostart_enabled() le
relit. La config ne mémorise que la préférence « démarrer réduit ».
"""

import os
import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "PixelToPath"


def autostart_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, _RUN_NAME)
                return True
        except OSError:
            return False
    if sys.platform == "linux":
        return _desktop_path().exists()
    return False


def set_autostart(enabled: bool, minimized: bool = False) -> bool:
    """Installe ou retire l'artefact. False = échec (droits, OS non câblé)."""
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ,
                                      _launch_command(minimized))
                else:
                    try:
                        winreg.DeleteValue(key, _RUN_NAME)
                    except FileNotFoundError:
                        pass  # déjà absent : objectif atteint
            return True
        except OSError:
            return False
    if sys.platform == "linux":
        desktop = _desktop_path()
        try:
            if enabled:
                desktop.parent.mkdir(parents=True, exist_ok=True)
                tmp = desktop.with_name(desktop.name + ".tmp")
                tmp.write_text(_desktop_text(_launch_command(minimized)),
                               encoding="utf-8")
                os.replace(tmp, desktop)  # écriture atomique
            else:
                desktop.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    return False


def _desktop_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(base) / "autostart" / f"{_RUN_NAME}.desktop"


def _launch_command(minimized: bool) -> str:
    """Commande absolue de lancement, exe cité, --minimized éventuel.

    Figeuré (exe installé) : sys.executable est l'exe PyInstaller. En
    dev : l'interpréteur + app.py — chemins absolus car le registre et
    le .desktop n'héritent pas du répertoire courant.
    """
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}"'
    else:
        app_py = Path(__file__).resolve().parent.parent / "app.py"
        command = f'"{sys.executable}" "{app_py}"'
    return f"{command} --minimized" if minimized else command


def _desktop_text(command: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={_RUN_NAME}\n"
        "Comment=Conversion image → SVG par lots\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "Categories=Utility;Graphics;\n"
    )
