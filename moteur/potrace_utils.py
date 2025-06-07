import subprocess
import shutil

def find_potrace():
    """
    Recherche l'exécutable 'potrace' sur le système.

    Cette fonction tente de localiser le binaire 'potrace' de manière fiable :
    1. En vérifiant s'il est accessible via le PATH système (`shutil.which`).
    2. En testant des emplacements courants sur Windows.
    3. Pour chaque chemin candidat, elle exécute `potrace --version` pour valider la présence de l'exécutable.

    Returns:
        str | None: Le chemin complet vers l'exécutable 'potrace' s'il est trouvé, sinon None.
    """
    
    # Vérifie si potrace est accessible dans le PATH système
    potrace_path = shutil.which("potrace")
    if potrace_path:
        return potrace_path

    # Emplacements connus de l'exécutable potrace sur Windows
    possible_paths = [
        r"C:\Program Files\Potrace\potrace.exe",
        r"C:\Program Files (x86)\Potrace\potrace.exe",
        r"C:\potrace\potrace.exe",
    ]
    
    # Teste chaque chemin candidat
    for path in possible_paths:
        try:
            result = subprocess.run(
                [path, '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return path
        except (subprocess.SubprocessError, FileNotFoundError):
            # Passe au chemin suivant si le binaire n'est pas valide ou introuvable
            continue  

    # Aucun binaire valide trouvé
    return None