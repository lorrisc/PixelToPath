from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt, QSize

class SvgPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #ccc;
                background-color: #fff;
            }
        """)
        self.setMinimumSize(50, 50)
        self.renderer = None
        self.message = "Aperçu SVG"

    def load_svg(self, path):
        self.renderer = QSvgRenderer(path)
        if not self.renderer.isValid():
            self.message = "Erreur de chargement SVG"
            self.renderer = None
        else:
            self.message = ""
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.renderer or not self.renderer.isValid():
            painter.drawText(self.rect(), Qt.AlignCenter, self.message)
            return

        widget_size = self.size()
        svg_size = self.renderer.defaultSize()
        if svg_size.isEmpty():
            svg_size = QSize(200, 200)

        scale_x = widget_size.width() / svg_size.width()
        scale_y = widget_size.height() / svg_size.height()

        # Pour respecter le ratio, utiliser le plus petit scale et centrer
        scale = min(scale_x, scale_y)
        final_width = svg_size.width() * scale
        final_height = svg_size.height() * scale
        x = (widget_size.width() - final_width) / 2
        y = (widget_size.height() - final_height) / 2

        painter.translate(x, y)
        painter.scale(scale, scale)
        self.renderer.render(painter)
        painter.end()