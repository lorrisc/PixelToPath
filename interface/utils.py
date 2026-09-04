import os
import subprocess
import sys

def resource_path(relative_path):
    """Renvoie le chemin absolu vers une ressource, compatible PyInstaller."""
    if getattr(sys, 'frozen', False):  # PyInstaller
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def open_directory(path: str) -> bool:
    """Ouvre un dossier dans le gestionnaire de fichiers du système.

    Renvoie True si l'ouverture a été demandée, False si le chemin
    n'existe pas ou que le lanceur a échoué.
    """
    if not path or not os.path.isdir(path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 — exploration, pas exécution
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        return False
    return True