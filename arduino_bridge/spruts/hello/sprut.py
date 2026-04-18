"""
Hello Sprut — PROJ-6 example
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from arduino_bridge.plugins.sprut_base import SprutBase

class SprutWidget(SprutBase, QWidget):
    def __init__(self, manifest, hull_api=None):
        SprutBase.__init__(self, manifest, hull_api)
        QWidget.__init__(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel(f"Hallo von {self.manifest.name}!")
        label.setStyleSheet("color: #E0E0E0; font-size: 12pt; padding: 8px;")
        layout.addWidget(label)

    def get_widget(self):
        return self
