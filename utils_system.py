import sys
import shutil
import subprocess
import os

def get_potrace_path():
    if sys.platform == "win32":
        # chemin local dans l’exe
        return os.path.join(sys._MEIPASS, "bin/potrace-bin/potrace.exe") if getattr(sys, 'frozen', False) else "bin/potrace-bin/potrace.exe"
    else:
        # Linux/macOS : on cherche dans le PATH
        potrace = shutil.which("potrace")
        if not potrace:
            raise FileNotFoundError("potrace non trouvé")
        return potrace
