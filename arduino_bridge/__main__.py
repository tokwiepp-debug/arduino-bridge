"""
ArduinoBridge — Main Entry Point
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication
from arduino_bridge.ui.main_window import ArduinoBridgeWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s — %(message)s"
)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ArduinoBridge")
    
    window = ArduinoBridgeWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
