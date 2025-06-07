from PyQt5.QtWidgets import QLabel, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

class DropZone(QLabel):
    imageDropped = pyqtSignal(QPixmap, str)  # signal avec l'image pixmap ET chemin

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #4F6D7A;
                background-color: #EEEEEE;
                color: #555;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Déposez une image PNG ici\nou cliquez pour ouvrir")
        self.setAcceptDrops(True)
        self.image = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".png"):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and len(urls) == 1:
            filepath = urls[0].toLocalFile()
            if filepath.lower().endswith(".png"):
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    self.setPixmap(pixmap.scaled(
                        self.width(), self.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
                    self.image = pixmap
                    self.imageDropped.emit(pixmap, filepath)
                else:
                    self.setText("Erreur : impossible de charger l'image")
            else:
                self.setText("Veuillez déposer une image PNG")
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Ouvrir une image PNG", "", "Images PNG (*.png)"
            )
            if filepath:
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    self.setPixmap(pixmap.scaled(
                        self.width(), self.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
                    self.image = pixmap
                    self.imageDropped.emit(pixmap, filepath) 