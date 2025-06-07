import os
import sys
import logging

from moteur.logging_config import setup_logging
from utils.potrace_utils import find_potrace
from utils.file_utils import choose_file_interactively, process_file

def main():
    setup_logging()

    # Vérifier potrace
    potrace_path = find_potrace()
    if not potrace_path:
        logging.error("Potrace non trouvé !")
        logging.info("Vérifiez que 'potrace.exe' est bien installé et accessible.")
        sys.exit(1)
    logging.info("Potrace détecté !")

    # Vérification / création des dossiers input/output
    input_folder = "input"
    output_folder = "output"

    if not os.path.isdir(input_folder):
        logging.error(f"Dossier d'entrée '{input_folder}' introuvable.")
        sys.exit(1)
    if not os.path.isdir(output_folder):
        logging.info(f"Dossier de sortie '{output_folder}' introuvable, création...")
        os.makedirs(output_folder, exist_ok=True)

    # Chercher tous les PNG dans input
    png_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.png')]

    if not png_files:
        logging.error(f"Aucun fichier PNG trouvé dans le dossier '{input_folder}'.")
        sys.exit(1)

    choice_num = choose_file_interactively(png_files)

    if choice_num == 0:
        # Tous les fichiers
        files_to_process = [os.path.join(input_folder, f) for f in png_files]
    else:
        # Un seul fichier choisi
        chosen_file = png_files[choice_num - 1]
        files_to_process = [os.path.join(input_folder, chosen_file)]

    # Traiter les fichiers
    for png_path in files_to_process:
        logging.info(f"Utilisation de {os.path.basename(png_path)}")
        process_file(potrace_path, png_path, output_folder)
    

if __name__ == "__main__":
    main()