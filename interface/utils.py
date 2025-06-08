import os
import sys

def resource_path(relative_path):
    """Renvoie le chemin absolu vers une ressource, compatible PyInstaller."""
    if getattr(sys, 'frozen', False):  # PyInstaller
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)