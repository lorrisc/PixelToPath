from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt

class PreviewPanel(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #4F6D7A;
                background-color: #EEEEEE;
                color: #555;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Aperçu modifié")

    def update_image(self, pixmap):
        if pixmap:
            self.setPixmap(pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            self.setText("Aperçu modifié")
