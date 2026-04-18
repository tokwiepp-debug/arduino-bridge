"""
Main Window — PROJ-4
ArduinoBridge main window with dark theme.
"""

import logging
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QLineEdit, QProgressBar, QTextEdit, QStatusBar, QMenuBar, QMenu, QFileDialog, QCheckBox, QToolBar
from PyQt6.QtGui import QAction

from .theme import DARK_STYLESHEET, UI_STRINGS
from ..core import PortScanner, BoardDetector

logger = logging.getLogger("arduino_bridge.main_window")

class ArduinoBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(UI_STRINGS["app_title"])
        self.setMinimumSize(800, 600)
        self.setStyleSheet(DARK_STYLESHEET)

        self.scanner = PortScanner()
        self.detector = BoardDetector()
        self._flash_process = None
        self._last_ports = []

        self._init_ui()
        self._init_menu()
        self._scan_ports()
        QTimer.singleShot(0, self._start_auto_refresh)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Port selector
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        self.refresh_btn = QPushButton(UI_STRINGS["refresh_btn"])
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.clicked.connect(self._scan_ports)
        self.auto_refresh_cb = QCheckBox(UI_STRINGS["auto_refresh_cb"])

        toolbar.addWidget(QLabel(UI_STRINGS["port_label"]))
        toolbar.addWidget(self.port_combo)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.auto_refresh_cb)

        # Board info
        self.board_label = QLabel(UI_STRINGS["board_unknown"])
        self.board_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0; padding: 4px;")
        layout.addWidget(self.board_label)

        # Firmware
        firmware_layout = QHBoxLayout()
        firmware_layout.addWidget(QLabel(UI_STRINGS["firmware_label"]))
        self.hex_path_edit = QLineEdit()
        self.hex_path_edit.setPlaceholderText(UI_STRINGS["select_hex"])
        firmware_layout.addWidget(self.hex_path_edit)
        self.browse_btn = QPushButton(UI_STRINGS["browse_btn"])
        self.browse_btn.setFixedWidth(100)
        self.browse_btn.clicked.connect(self._browse_hex)
        firmware_layout.addWidget(self.browse_btn)
        layout.addLayout(firmware_layout)

        # Flash buttons
        btn_layout = QHBoxLayout()
        self.flash_btn = QPushButton(UI_STRINGS["flash_btn"])
        self.flash_btn.setFixedWidth(120)
        self.flash_btn.clicked.connect(self._do_flash)
        self.cancel_btn = QPushButton(UI_STRINGS["cancel_btn"])
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.flash_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Log
        layout.addWidget(QLabel(UI_STRINGS["log_label"]))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        layout.addWidget(self.log_output)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(UI_STRINGS["status_ready"])

    def _init_menu(self):
        menubar = self.menuBar()
        datei_menu = menubar.addMenu(UI_STRINGS["menu_file"])
        exit_action = QAction(UI_STRINGS["menu_exit"], self)
        exit_action.triggered.connect(self.close)
        datei_menu.addAction(exit_action)

        hilfe_menu = menubar.addMenu(UI_STRINGS["menu_help"])
        about_action = QAction(UI_STRINGS["menu_about"], self)
        about_action.triggered.connect(self._show_about)
        hilfe_menu.addAction(about_action)

    def _show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, UI_STRINGS["menu_about"],
            "ArduinoBridge v1.0.0\n\nDesktop-Tool für Arduino-Firmware-Flash\n\nMade with ❤️ for Tobi")

    def _scan_ports(self):
        ports = self.scanner.scan()
        self._last_ports = ports
        self.port_combo.clear()
        for p in ports:
            label = f"{p.name} — {p.description}"
            if p.in_use:
                label += " (belegt)"
            self.port_combo.addItem(label, p.name)
        if ports:
            self.port_combo.setCurrentIndex(0)
            self._update_board_info()
        else:
            self.board_label.setText(UI_STRINGS["no_ports"])

    def _update_board_info(self):
        idx = self.port_combo.currentIndex()
        if idx < 0:
            return
        port_name = self.port_combo.currentData()
        port_info = next((p for p in self._last_ports if p.name == port_name), None)
        if not port_info:
            return
        board = self.detector.detect(port_info)
        if board:
            self.board_label.setText(
                f"Board: {board.name} — {board.board_type} — {board.flash_tool}"
            )
        else:
            self.board_label.setText(
                f"⚠ {UI_STRINGS['board_unknown_port'].format(port=port_name)} — {port_info.hwid}"
            )

    def _start_auto_refresh(self):
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self._scan_ports)
        self._auto_timer.start(3000)

    def _browse_hex(self):
        path, _ = QFileDialog.getOpenFileName(
            self, UI_STRINGS["select_hex"], "", UI_STRINGS["hex_filter"]
        )
        if path:
            self.hex_path_edit.setText(path)

    def _do_flash(self):
        self.log_output.append("[INFO] Flashen noch nicht implementiert")
        self.status_bar.showMessage("Flash: PROJ-3")

    def log(self, message: str, level: str = "INFO"):
        self.log_output.append(f"[{level}] {message}")

    def closeEvent(self, event):
        if hasattr(self, '_auto_timer'):
            self._auto_timer.stop()
        event.accept()
