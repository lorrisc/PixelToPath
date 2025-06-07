from PyQt5.QtWidgets import QWidget, QFormLayout, QCheckBox, QSlider, QLabel
from PyQt5.QtCore import Qt

class ControlPanel(QWidget):
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback

        self.setStyleSheet("""
            QFormLayout {
                margin: 20px;
            }
            QLabel {
                color: black;
                padding-bottom: 4px;
                font-size:13px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #4F6D7A;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #C0D6DF;
                border: 1px solid #4F6D7A;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #4F6D7A;
            }
            QCheckBox {
                spacing: 8px;
                font-size:13px;
                color: black;
                           
            }
        """)

        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignLeft)
        layout.setFormAlignment(Qt.AlignTop)
        layout.setVerticalSpacing(15)
        layout.setHorizontalSpacing(20)

        self.slider_turdsize = QSlider(Qt.Horizontal)
        self.slider_turdsize.setRange(0, 10)
        self.slider_turdsize.setValue(2)
        self.slider_turdsize.valueChanged.connect(lambda _: self.update_callback())

        self.slider_alphamax = QSlider(Qt.Horizontal)
        self.slider_alphamax.setRange(0, 1334)
        self.slider_alphamax.setValue(1000)
        self.slider_alphamax.valueChanged.connect(self.on_slider_alphamax_changed)

        self.slider_threshold = QSlider(Qt.Horizontal)
        self.slider_threshold.setRange(0, 255)
        self.slider_threshold.setValue(128)
        self.slider_threshold.valueChanged.connect(lambda _: self.update_callback())

        self.checkbox_threshold = QCheckBox("Seuil automatique")
        self.checkbox_threshold.stateChanged.connect(lambda _: self.update_callback())

        self.checkbox_invert = QCheckBox("Inverser les couleurs")
        self.checkbox_invert.stateChanged.connect(lambda _: self.update_callback())

        layout.addRow("Taille minimale (Turdsize)", self.slider_turdsize)
        layout.addRow("Lissage (Alphamax)", self.slider_alphamax)
        layout.addRow("Seuil (Threshold)", self.slider_threshold)
        layout.addRow("", self.checkbox_threshold)
        layout.addRow("", self.checkbox_invert)

        self.setLayout(layout)

    def on_slider_alphamax_changed(self):
        real_value = self.slider_alphamax.value() / 1000
        self.update_callback()

    def get_params(self):
        return {
            "slider_turdsize": self.slider_turdsize.value(),
            "slider_alphamax": self.slider_alphamax.value() / 1000,
            "slider_threshold": self.slider_threshold.value(),
            "checkbox_threshold": self.checkbox_threshold.isChecked(),
            "checkbox_invert": self.checkbox_invert.isChecked(),
        }
