import sys
import shutil
import subprocess
import os

def get_potrace_path():
    if sys.platform == "win32":
        # chemin local dans l’exe
        return os.path.join(sys._MEIPASS, "bin/potrace-bin/potrace.exe") if getattr(sys, 'frozen', False) else "bin/potrace-bin/potrace.exe"
    else:
        # Si l'app est packagée, on fournit notre propre binaire
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, "bin/potrace-1.16.linux-x86_64/potrace")
        # En développement, on utilise le binaire local s’il existe
        local_path = "bin/potrace-1.16.linux-x86_64/potrace"
        if os.path.exists(local_path):
            return local_path
        # Sinon, on cherche dans le PATH
        potrace = shutil.which("potrace")
        if not potrace:
            raise FileNotFoundError("potrace non trouvé")
        return potrace
