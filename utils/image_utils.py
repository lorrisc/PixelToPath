import numpy as np
from PIL import Image
import re

def png_to_pbm(png_path, pbm_path, threshold=128, invert=False, preview=False):
    """
    Convertit un PNG en PBM (Portable Bitmap) pour potrace
    
    Args:
        png_path (str): Chemin vers le PNG source
        pbm_path (str): Chemin de sortie PBM
        threshold (int|str): Seuil de binarisation (0-255, ou "auto", défaut: 128).
        invert (bool): Inverser noir/blanc (défaut: False)
        preview (bool): Sauvegarder une preview PNG du résultat (défaut: False)

    Returns:
        tuple: La taille de l'image binaire sous forme de tuple (largeur, hauteur).
    """
    with Image.open(png_path) as img:
        # Gérer la transparence
        if img.mode in ('RGBA', 'LA'):
            # Créer un fond blanc pour les zones transparentes
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])  # Utilise le canal alpha
            else:
                background.paste(img, mask=img.split()[-1])
            img = background
        
        # Convertir en niveaux de gris
        if img.mode != 'L':
            img = img.convert('L')
        
        # Analyser l'histogramme pour ajuster automatiquement le seuil
        img_array = np.array(img)
        hist, bins = np.histogram(img_array, bins=256, range=(0, 256))
        
        # Trouver un seuil automatique si threshold est "auto"
        if threshold == "auto":
            # Méthode d'Otsu simplifiée
            total_pixels = img_array.size
            sum_total = np.sum(np.arange(256) * hist)
            
            max_variance = 0
            threshold = 128
            
            w0 = 0
            sum0 = 0
            
            for t in range(256):
                w0 += hist[t]
                if w0 == 0:
                    continue
                
                w1 = total_pixels - w0
                if w1 == 0:
                    break
                
                sum0 += t * hist[t]
                mean0 = sum0 / w0
                mean1 = (sum_total - sum0) / w1
                
                variance = w0 * w1 * (mean0 - mean1) ** 2
                
                if variance > max_variance:
                    max_variance = variance
                    threshold = t
            
        # Appliquer le seuillage
        if invert:
            # Inverser : les zones claires deviennent noires
            binary_array = (img_array < threshold).astype(np.uint8) * 255
        else:
            # Normal : les zones sombres deviennent noires
            binary_array = (img_array >= threshold).astype(np.uint8) * 255
        
        # Créer l'image binaire
        binary_img = Image.fromarray(binary_array, mode='L')
        
        # Sauvegarder une preview si demandé
        if preview:
            preview_path = pbm_path.replace('.pbm', '_preview.png')
            print(f"Preview PBM : {preview_path}")
            binary_img.save(preview_path)
        
        # Sauvegarder en format PBM
        width, height = binary_img.size
        
        with open(pbm_path, 'wb') as f:
            # En-tête PBM
            f.write(f"P4\n{width} {height}\n".encode())
            
            # Données binaires (1 bit par pixel, packés par bytes)
            for y in range(height):
                bits = []
                for x in range(width):
                    pixel = binary_img.getpixel((x, y))
                    # Potrace : 0 = noir (forme à vectoriser), 1 = blanc (fond)
                    # Si pixel est blanc (255) -> bit = 1 (fond)
                    # Si pixel est noir (0) -> bit = 0 (forme)
                    bits.append(1 if pixel > 127 else 0)
                
                # Grouper par 8 bits (1 byte)
                for i in range(0, len(bits), 8):
                    byte_bits = bits[i:i+8]
                    # Compléter avec des 1 si nécessaire
                    while len(byte_bits) < 8:
                        byte_bits.append(1)
                    
                    # Convertir en byte
                    byte_value = 0
                    for j, bit in enumerate(byte_bits):
                        byte_value |= (bit << (7 - j))
                    
                    f.write(bytes([byte_value]))
        
        return binary_img.size


def optimize_svg(svg_path):
    """
    Optimise le SVG généré en supprimant les espaces inutiles et les nouvelles lignes superflues.

    Args:
        svg_path (str): Chemin vers le fichier SVG à optimiser.

    Returns:
        bool: True si l'optimisation a réussi, False sinon.
    """
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Utiliser des expressions régulières pour supprimer les espaces et nouvelles lignes superflues
        content = re.sub(r'\s+', ' ', content)  # Remplace les espaces multiples par un seul espace
        content = re.sub(r'>\s+<', '><', content)  # Supprime les espaces entre les balises

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"SVG optimisé : {svg_path}")
        return True

    except Exception as e:
        print(f"Erreur lors de l'optimisation : {e}")
        return False
