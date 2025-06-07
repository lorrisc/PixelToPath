import os

from utils.potrace_utils import png_to_svg_potrace
from utils.image_utils import optimize_svg

def choose_file_interactively(png_files):
    """
    Permet à l'utilisateur de choisir un fichier PNG parmi une liste ou de traiter tous les fichiers.

    Args:
        png_files (list): Liste des chemins de fichiers PNG disponibles.

    Returns:
        int: Numéro du fichier choisi par l'utilisateur, ou 0 pour traiter tous les fichiers.
    """
    print("\nFichiers PNG disponibles dans 'input' :")
    for idx, f in enumerate(png_files, start=1):
        print(f"  {idx}. {f}")
    print("  0. Traiter tous les fichiers")

    while True:
        choice = input("Choisissez un numéro (0 pour tous) : ").strip()
        if choice.isdigit():
            choice_num = int(choice)
            if 0 <= choice_num <= len(png_files):
                print('\n')
                return choice_num
        print(f"Choix invalide. Veuillez entrer un numéro entre 0 et {len(png_files)}.")


import os

def process_file(potrace_path, png_path, output_folder):
    """
    Traite un fichier PNG pour générer plusieurs versions vectorisées en SVG avec différentes configurations.

    Args:
        potrace_path (str): Chemin vers l'exécutable potrace.
        png_path (str): Chemin vers le fichier PNG à traiter.
        output_folder (str): Dossier de sortie pour les fichiers SVG générés.

    Returns:
        list: Liste des chemins des fichiers SVG générés.
    """
    try:
        filename_with_ext = os.path.basename(png_path)
        filename = os.path.splitext(filename_with_ext)[0]

        # Définir les configurations pour chaque version SVG
        svg_configurations = {
            'normal': {'turdsize': 2, 'alphamax': 1.0, 'threshold': 128, 'invert': False, 'version_name': "normale"},
            'inverted': {'turdsize': 2, 'alphamax': 1.0, 'threshold': 128, 'invert': True, 'version_name': "inversée (pour les images claires)"},
            'auto': {'turdsize': 2, 'alphamax': 1.0, 'threshold': "auto", 'invert': False, 'version_name': "seuil automatique"},
            'smooth': {'turdsize': 4, 'alphamax': 0.5, 'threshold': 120, 'invert': False, 'version_name': "lissée"},
            'perso': {'turdsize': 2, 'alphamax': 1, 'threshold': 240, 'invert': True, 'version_name': "perso"}
        }

        svg_files = []

        # Génération des fichiers SVG
        for suffix, config in svg_configurations.items():
            svg_path = os.path.join(output_folder, f"{filename}_{suffix}.svg")
            svg_file = png_to_svg_potrace(
                potrace_path=potrace_path,
                png_path=png_path,
                svg_path=svg_path,
                turdsize=config['turdsize'],
                alphamax=config['alphamax'],
                threshold=config['threshold'],
                invert=config['invert'],
                version_name=config['version_name']
            )
            svg_files.append(svg_file)

        # Optimisation des fichiers SVG
        for svg_file in svg_files:
            optimize_svg(svg_file)

        return svg_files

    except Exception as e:
        print(f"Erreur lors du traitement du fichier : {e}")
        return []