import subprocess
import shutil
import os
import tempfile
import logging

from utils.image_utils import png_to_pbm

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


def png_to_svg_potrace(potrace_path, png_path, svg_path, turdsize=2, alphamax=1.0, threshold=128, 
                      invert=False, preview=True, version_name=""):
    """
    Vectorise un PNG en SVG en utilisant potrace
    
    Args:
        potrace_path (str): Chemin vers l'exécutable 'potrace'
        png_path (str): Chemin vers le fichier PNG
        svg_path (str): Chemin de sortie SVG
        turdsize (int): Supprime les particules de taille inférieure (défaut: 2)
        alphamax (float): Seuil de lissage des coins (0-1.334, défaut: 1.0)
        threshold (int|str): Seuil de binarisation (0-255, ou "auto", défaut: 128)
        invert (bool): Inverser noir/blanc (défaut: False)
        preview (bool): Créer une preview de la binarisation (défaut: True)
        version_name (str): Nom de la version généré (défaut: "")
    
    Returns:
        str: Chemin du fichier SVG créé
    """

    if version_name != "":
        logging.info(f"Vectorisation de la version {version_name}...")
    else:
        logging.info(f"Vectorisation en cours...")
    
    # Créer un fichier PBM temporaire
    with tempfile.NamedTemporaryFile(suffix='.pbm', delete=False) as temp_pbm:
        temp_pbm_path = temp_pbm.name
    
    try:
        # Conversion PNG en PBM temporaire
        dimensions = png_to_pbm(png_path, temp_pbm_path, threshold, invert, preview)
        
        cmd = [
            potrace_path,
            '--svg',
            '--output', svg_path,
            '--turdsize', str(turdsize),
            '--alphamax', str(alphamax),
            '--tight',  # Ajuste automatiquement la taille
            temp_pbm_path
        ]
        
        # Exécuter Potrace
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logging.error(f"Erreur potrace stdout : {result.stdout}")
            logging.error(f"Erreur potrace stderr : {result.stderr}")
            raise RuntimeError(f"Erreur potrace (code {result.returncode}): {result.stderr}")
        
        logging.info(f"Vectorisation réussie : {png_path} -> {svg_path}")
        
        return svg_path
        
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(temp_pbm_path):
            os.remove(temp_pbm_path)
