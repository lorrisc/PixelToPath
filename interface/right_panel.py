from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFileDialog, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt

from interface.widgets.DropZone import DropZone
from interface.widgets.ControlPanel import ControlPanel
from interface.widgets.PreviewPanel import PreviewPanel
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtSvg import QSvgWidget

import subprocess
import logging
import os
import tempfile

from moteur.utils.image_utils import png_to_pbm
from interface.widgets.SvgPreview import SvgPreview 

class RightPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.setup_part1()
        self.setup_part2()
        self.setup_part3()

        # ==== GLOBAL LAYOUT ====
        v_layout = QVBoxLayout()
        v_layout.setSpacing(5)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.addWidget(self.part1, 40)
        v_layout.addWidget(self.part2, 20)
        v_layout.addWidget(self.part3, 40)

        self.setLayout(v_layout)

        # ==== STATE ====
        self.original_pixmap = None
        self.modified_pixmap = None
        self.original_png_path = None
        self.temp_pbm_path = None
        self.temp_svg_path = None

    def setup_part1(self):
        self.part1 = QWidget()
        h_layout_part1 = QHBoxLayout()
        h_layout_part1.setSpacing(10)
        h_layout_part1.setContentsMargins(0, 0, 0, 0)

        # Création des trois éléments
        self.dropzone = DropZone(self)
        self.dropzone.imageDropped.connect(self.image_dropped)

        self.control_panel = ControlPanel(self.apply_changes)

        self.preview_panel = PreviewPanel()

        # Ajout des éléments
        h_layout_part1.addWidget(self.dropzone, 1)
        h_layout_part1.addWidget(self.control_panel, 1)
        h_layout_part1.addWidget(self.preview_panel, 1)

        self.part1.setLayout(h_layout_part1)
    
    def create_vectorize_button(self):
        button = QPushButton("Vectoriser")
        button.setCursor(Qt.PointingHandCursor)

        button.setStyleSheet("""
            QPushButton {
                background-color: #c0d6df;
                color: black;
                font-weight: bold;
                padding: 15px 50px;
                border-radius: 4px;
                font-size: 14px;
                border: 1px solid #4F6D7A;
            }
        """)
        button.clicked.connect(self.vectorize_image)
        return button

    def setup_part2(self):
        self.part2 = QWidget()
        v2_layout = QVBoxLayout()
        self.vectorize_button = self.create_vectorize_button()
        v2_layout.addStretch()
        v2_layout.addWidget(self.vectorize_button, alignment=Qt.AlignCenter)
        v2_layout.addStretch()
        self.part2.setLayout(v2_layout)

    def setup_part3(self):
        self.part3 = QWidget()
        self.part3.setStyleSheet("border: 1px solid #4F6D7A;")

        # SvgPreview avec style (sans taille fixe)
        self.svg_widget = SvgPreview()
        self.svg_widget.setStyleSheet("background-color: #EEEEEE; border: 1px solid #4F6D7A;")

        # Le widget qui force un ratio 1:1 sans taille fixe
        svg_wrapper = QWidget()
        svg_layout = QVBoxLayout()
        svg_layout.setContentsMargins(0, 0, 0, 0)
        svg_layout.addWidget(self.svg_widget)
        svg_wrapper.setLayout(svg_layout)

        # Appliquer une contrainte de carré via resizeEvent
        class SquareWidget(QWidget):
            def resizeEvent(self, event):
                size = min(event.size().width(), event.size().height())
                self.svg_widget.resize(size, size)
                super().resizeEvent(event)

        svg_container = SquareWidget()
        svg_container.svg_widget = self.svg_widget  # référence pour resizeEvent
        svg_container.setLayout(svg_layout)


        # Bouton Télécharger SVG
        self.download_svg_button = QPushButton("Télécharger SVG")
        self.download_svg_button.setCursor(Qt.PointingHandCursor)
        self.download_svg_button.setEnabled(False)
        self.download_svg_button.clicked.connect(self.save_svg)
        self.download_svg_button.setStyleSheet("""
            QPushButton {
                background-color: #c0d6df;
                color: black;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 4px;
                font-size: 14px;
                border: 1px solid #4F6D7A;
            }
        """)

        right_layout = QVBoxLayout()
        right_layout.addStretch()
        right_layout.addWidget(self.download_svg_button, alignment=Qt.AlignCenter)
        right_layout.addStretch()

        h3_layout = QHBoxLayout()
        h3_layout.addWidget(svg_container)
        h3_layout.addLayout(right_layout)

        h3_layout.setStretch(0, 1)  # svg_container - gauche, 50%
        h3_layout.setStretch(1, 1)  # right_layout - droite, 50%
        h3_layout.setSpacing(30)

        self.part3.setLayout(h3_layout)

        self.part3.setLayout(h3_layout)

    def image_dropped(self, pixmap, filepath):
        self.original_pixmap = pixmap
        self.modified_pixmap = pixmap.copy()
        self.original_png_path = filepath
        self.preview_panel.update_image(self.modified_pixmap)
        self.apply_changes()

    def apply_changes(self):
        if not self.original_pixmap or not self.original_png_path:
            print("Aucune image d'origine chargée")
            return

        # Récupération des paramètres
        params = self.control_panel.get_params()
        print("Params appliqués :", params)

        # Mise à jour locale de l'image modifiée
        self.modified_pixmap = self.original_pixmap.copy()

        # Création fichier temporaire PBM
        with tempfile.NamedTemporaryFile(suffix='.pbm', delete=False) as temp_pbm:
            self.temp_pbm_path = temp_pbm.name  # 🔁 Stockage du chemin pour vectorisation

        # Construction du chemin preview PNG (ex: tmpabc123_preview.png)
        self.temp_preview_path = self.temp_pbm_path.replace('.pbm', '_preview.png')

        # Conversion PNG vers PBM
        dimensions = png_to_pbm(
            self.original_png_path,
            self.temp_pbm_path,
            threshold=params['slider_threshold'],
            invert=params['checkbox_invert'],
            preview=True
        )

        print(f"Image convertie en PBM : {self.temp_pbm_path}")
        print(f"Image preview : {self.temp_preview_path} avec dimensions {dimensions}")

        # Charger et afficher la preview dans le panneau de droite
        preview_pixmap = QPixmap(self.temp_preview_path)
        if not preview_pixmap.isNull():
            self.preview_panel.update_image(preview_pixmap)
        else:
            print("Erreur : impossible de charger l'image preview")


    def vectorize_image(self):
        if not self.temp_pbm_path:
            print("Erreur: Pas de fichier PBM disponible.")
            return

        # Récupérer paramètres pour potrace
        params = self.control_panel.get_params()
        print(params)
        turdsize = params['slider_turdsize']
        alphamax = params['slider_alphamax']

        # Préparer fichier SVG temporaire
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as temp_svg:
            self.temp_svg_path = temp_svg.name

        potrace_path = "potrace"  # adapter si besoin le chemin complet

        cmd = [
            potrace_path,
            '--svg',
            '--output', self.temp_svg_path,
            '--turdsize', str(turdsize),
            '--alphamax', str(alphamax),
            '--tight',
            self.temp_pbm_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Erreur potrace stdout : {result.stdout}")
            logging.error(f"Erreur potrace stderr : {result.stderr}")
            print(f"Erreur durant la vectorisation : {result.stderr}")
            return

        print(f"Vectorisation réussie : {self.temp_svg_path}")

        # Afficher SVG dans part3 - CORRECTION ICI
        self.display_svg(self.temp_svg_path)
        self.download_svg_button.setEnabled(True)


    def display_svg(self, svg_path):
        """Affiche le SVG dans le widget d'aperçu"""
        print(f"Affichage SVG : {svg_path}")
        
        # Vérifier que le fichier existe
        if not os.path.exists(svg_path):
            print(f"Erreur: le fichier SVG n'existe pas : {svg_path}")
            return
        
        self.svg_widget.load_svg(svg_path)


    def save_svg(self):
        print('bonjour')
        if not self.temp_svg_path:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder SVG", "", "Fichiers SVG (*.svg)")
        if save_path:
            try:
                with open(self.temp_svg_path, 'rb') as f_src, open(save_path, 'wb') as f_dst:
                    f_dst.write(f_src.read())
                print(f"SVG sauvegardé dans {save_path}")
            except Exception as e:
                print(f"Erreur lors de la sauvegarde: {e}")



