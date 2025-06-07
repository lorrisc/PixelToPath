from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout

from interface.left_panel import LeftPanel
from interface.right_panel import RightPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelToPath - Transform PNG image to SVG")
        self.setGeometry(100, 100, 1500, 800)

        # https://coolors.co/palette/dd6e42-e8dab2-4f6d7a-c0d6df-eaeaea
        central = QWidget()
        central.setStyleSheet("background-color: #eaeaea;")
        self.setCentralWidget(central)

        h_layout = QHBoxLayout()
        h_layout.setSpacing(50)
        central.setLayout(h_layout)

        self.left_panel = LeftPanel()
        h_layout.addWidget(self.left_panel)

        self.right_panel = RightPanel()
        h_layout.addWidget(self.right_panel)