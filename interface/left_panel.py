from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class LeftPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(400)

        description = (
            "<b>PixelToPath</b><br>"
            "Cette application transforme vos images PNG en graphiques vectoriels SVG de haute qualité en utilisant Potrace. "
            "L'image est d'abord convertie en noir et blanc pour faciliter la vectorisation, avec plusieurs options pour ajuster le rendu final.<br><br>"
            "<b>Paramètres :</b><br>"
            "<b>Turdsize</b> : Ignore les petits objets en dessous de cette taille (en pixels). Augmenter pour supprimer le bruit.<br>"
            "<b>Alphamax</b> : Contrôle la courbure des contours vectoriels. Valeur plus élevée = contours plus lisses.<br>"
            "<b>Threshold</b> : Seuil de binarisation manuel. Les pixels au-dessus deviennent blancs, en dessous noirs.<br>"
            "<b>Threshold Auto</b> : Active la détection automatique du seuil idéal pour la binarisation.<br>"
            "<b>Invert</b> : Inverse les couleurs de l'image avant vectorisation (noir devient blanc et vice versa)."
        )

        label = QLabel(description)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)

        font = QFont()
        font.setPointSize(11)
        label.setFont(font)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addStretch()
        self.setLayout(layout)