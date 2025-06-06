# Vectoriseur PNG vers SVG avec Potrace

Ce script Python permet de vectoriser des images au format PNG en fichiers SVG en utilisant l'outil Potrace. Il offre plusieurs options pour ajuster la qualité et le style de la vectorisation.

## Prérequis

- Système Windows
- Python 3.x
- Bibliothèque Python Pillow (`pip install Pillow`)
- Bibliothèque Python NumPy (`pip install numpy`)
- Potrace installé et accessible dans votre système

## Installation

1. Assurez-vous que Python est installé sur votre système.
2. Installez les bibliothèques nécessaires avec pip :

```bash
pip install Pillow numpy
```

3. Téléchargez et installez Potrace depuis le [site officiel](https://potrace.sourceforge.net/) ou via un gestionnaire de paquets comme apt-get ou brew.

## Utilisation

1. Placez votre fichier PNG dans un répertoire "input".
2. Exécutez le script :

```bash
python script.py
```

3. Le script analysera l'image et générera plusieurs versions SVG avec différents paramètres pour vous permettre de choisir la meilleure option.

## Fonctions

- **find_potrace() :** Localise l'exécutable Potrace sur votre système.
png_to_pbm(png_path, pbm_path, threshold=128, invert=False, preview=False) : Convertit une image PNG en PBM pour la vectorisation.

- **png_to_svg_potrace(potrace_path, png_path, svg_path, turdsize=2, alphamax=1.0, threshold=128, invert=False, preview=True, version_name="") :** Vectorise une image PNG en SVG en utilisant Potrace.
  
- **optimize_svg(svg_path) :** Optimise le fichier SVG généré en supprimant les espaces inutiles.

## Conseils

Vérifiez les fichiers **_preview.png** pour voir la binarisation avant la vectorisation.
Si le résultat contient trop de blanc, essayez la version inversée.
Ajustez **turdsize** pour supprimer les petits détails indésirables.
Modifiez **alphamax** pour lisser les angles et obtenir des courbes plus douces.