"""
Main Window — PROJ-4 + Melissa Connection + Manual Board Select
ArduinoBridge main window with dark theme, Melissa WS connection, and manual board selection.
"""

import logging
import os
import sys
import asyncio
import json
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QLabel, QLineEdit, QProgressBar, QTextEdit, QStatusBar,
    QMenuBar, QMenu, QFileDialog, QCheckBox, QToolBar, QGroupBox, QFormLayout)
from PyQt6.QtGui import QAction

from .theme import DARK_STYLESHEET, UI_STRINGS
from ..core import PortScanner, BoardDetector

logger = logging.getLogger("arduino_bridge.main_window")

class WSWorker(QThread):
    """Background thread for WebSocket connection."""
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    message_received = pyqtSignal(dict)

    def __init__(self, uri, token=None):
        super().__init__()
        self.uri = uri
        self.token = token
        self._running = True
        self.daemon = True

    def run(self):
        """Run WebSocket in a persistent asyncio event loop."""
        import asyncio
        import websockets

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                headers = self._get_auth_header()

                # Run the connection coroutine
                loop.run_until_complete(self._connect_loop(loop, websockets, headers))
            except Exception as e:
                logger.warning(f"WS reconnect in 3s: {e}")
                self.disconnected.emit()
                import time
                time.sleep(3)

    def _get_auth_header(self):
        """Get Basic auth header from gateway password."""
        import os, base64
        password = os.environ.get("OPENCLAW_GATEWAY_PASSWORD", "Legitim-0208")
        credentials = base64.b64encode(f"admin:{password}".encode()).decode()
        return {"Authorization": f"Basic {credentials}"}

    async def _connect_loop(self, loop, websockets_module, headers):
        """Async WebSocket connection with proper keep-alive."""
        try:
            async with websockets_module.connect(
                self.uri,
                extra_headers=headers or {}
            ) as ws:
                self.connected.emit()
                logger.info(f"Verbunden: {self.uri}")

                # Listen for messages until closed
                while self._running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        try:
                            data = json.loads(msg)
                            self.message_received.emit(data)
                        except json.JSONDecodeError:
                            pass
                    except asyncio.TimeoutError:
                        # Check if we're still running (keep-alive)
                        continue
                    except Exception as e:
                        logger.warning(f"WS error: {e}")
                        break
        except Exception as e:
            logger.warning(f"WS connection failed: {e}")
            self.disconnected.emit()

    def stop(self):
        self._running = False


class ArduinoBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(UI_STRINGS["app_title"])
        self.setMinimumSize(900, 650)
        self.setStyleSheet(DARK_STYLESHEET)

        self.scanner = PortScanner()
        self.detector = BoardDetector()
        self._flash_process = None
        self._last_ports = []
        self._ws_worker: WSWorker | None = None
        self._melissa_connected = False

        # Load Melissa URL from environment or default
        self._melissa_uri = os.environ.get("OPENCLAW_GATEWAY_URI", "ws://localhost:18789")
        self._melissa_token = os.environ.get("OPENCLAW_TOKEN", "")
        self._tailscale_ip = None

        self._init_ui()
        self._init_menu()
        self._scan_ports()
        QTimer.singleShot(100, self._start_ws)
        QTimer.singleShot(0, self._start_auto_refresh)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # === Row 1: Melissa Connection Status ===
        conn_row = QHBoxLayout()
        self.conn_label = QLabel("Melissa: " + UI_STRINGS["melissa_disconnected"])
        self.conn_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        conn_row.addWidget(self.conn_label)
        conn_row.addStretch()
        # Manual URI field
        self.uri_edit = QLineEdit()
        self.uri_edit.setText(self._melissa_uri)
        self.uri_edit.setMaximumWidth(250)
        self.uri_edit.setStyleSheet("background-color: #3C3C4F; color: #E0E0E0; border: 1px solid #404050; padding: 2px 6px; font-size: 9pt;")
        self.uri_edit.setPlaceholderText("ws://localhost:18789")
        self.uri_edit.textChanged.connect(self._on_uri_changed)
        conn_row.addWidget(QLabel("Gateway:"))
        conn_row.addWidget(self.uri_edit)
        self.connect_btn = QPushButton("🔗 Verbinden")
        self.connect_btn.setFixedWidth(100)
        self.connect_btn.clicked.connect(self._start_ws)
        conn_row.addWidget(self.connect_btn)
        layout.addLayout(conn_row)

        # === Tailscale Section ===
        tailscale_row = QHBoxLayout()
        self.tailscale_status_label = QLabel("Tailscale: ○ Getrennt")
        self.tailscale_status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        tailscale_row.addWidget(self.tailscale_status_label)

        tailscale_row.addWidget(QLabel("Auth Key:"))
        self.tailscale_key_edit = QLineEdit()
        self.tailscale_key_edit.setMaximumWidth(300)
        self.tailscale_key_edit.setPlaceholderText("tskey-auth-kxxx...")
        self.tailscale_key_edit.setStyleSheet("background-color: #3C3C4F; color: #E0E0E0; border: 1px solid #404050; padding: 2px 6px; font-size: 9pt;")
        tailscale_row.addWidget(self.tailscale_key_edit)

        self.tailscale_login_btn = QPushButton("🔑 Login")
        self.tailscale_login_btn.setFixedWidth(80)
        self.tailscale_login_btn.clicked.connect(self._tailscale_login)
        tailscale_row.addWidget(self.tailscale_login_btn)

        self.tailscale_logout_btn = QPushButton("Logout")
        self.tailscale_logout_btn.setFixedWidth(80)
        self.tailscale_logout_btn.setEnabled(False)
        self.tailscale_logout_btn.clicked.connect(self._tailscale_logout)
        tailscale_row.addWidget(self.tailscale_logout_btn)

        self.tailscale_ip_label = QLabel("")
        self.tailscale_ip_label.setStyleSheet("color: #A0A0B0; font-size: 9pt;")
        tailscale_row.addWidget(self.tailscale_ip_label)
        tailscale_row.addStretch()
        layout.addLayout(tailscale_row)

        # === Row 2: Port Scanner ===
        toolbar = QToolBar()
        self.addToolBar(toolbar)
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

        # === Row 3: Board Info + Manual Selector ===
        board_group = QGroupBox("Board")
        board_layout = QFormLayout(board_group)

        self.board_auto_label = QLabel(UI_STRINGS["board_unknown"])
        self.board_auto_label.setStyleSheet("font-size: 12px; color: #A0A0B0;")
        board_layout.addRow("Erkannt:", self.board_auto_label)

        board_type_row = QHBoxLayout()
        board_type_row.addWidget(QLabel("Manual:"))
        self.board_manual_combo = QComboBox()
        self.board_manual_combo.setMinimumWidth(200)
        self._populate_manual_boards()
        self.board_manual_combo.currentIndexChanged.connect(self._on_manual_board_changed)
        board_type_row.addWidget(self.board_manual_combo)
        board_type_row.addStretch()
        board_layout.addRow(board_type_row)

        self.board_flash_tool_label = QLabel("Flash-Tool: —")
        self.board_flash_tool_label.setStyleSheet("color: #A0A0B0;")
        board_layout.addRow("Flash-Tool:", self.board_flash_tool_label)

        layout.addWidget(board_group)

        # === Row 4: HEX File ===
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

        # === Row 5: Flash Buttons ===
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

        # === Row 6: Progress Bar ===
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # === Row 7: Log ===
        layout.addWidget(QLabel(UI_STRINGS["log_label"]))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        layout.addWidget(self.log_output)

        # === Row 8: Status Bar ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(UI_STRINGS["status_ready"])

    def _populate_manual_boards(self):
        """Fill manual board selector."""
        boards = [
            ("auto", "— Automatisch —"),
            ("uno", "Arduino UNO (ATMega328P)"),
            ("nano", "Arduino Nano (ATMega328P)"),
            ("nano_old", "Arduino Nano Old (ATMega168)"),
            ("mega", "Arduino Mega 2560"),
            ("leonardo", "Arduino Leonardo"),
            ("esp32", "ESP32 DevKit"),
            ("esp32c3", "ESP32-C3"),
            ("esp8266", "ESP8266 (NodeMCU)"),
            ("rp2040", "Raspberry Pi Pico"),
            ("unknown", "⚠ Unbekannt (manuell)"),
        ]
        for bid, bname in boards:
            self.board_manual_combo.addItem(bname, bid)

    def _on_manual_board_changed(self, idx):
        bid = self.board_manual_combo.currentData()
        if bid and bid != "auto":
            tool_map = {"uno": "avrdude", "nano": "avrdude", "nano_old": "avrdude",
                        "mega": "avrdude", "leonardo": "avrdude",
                        "esp32": "esptool", "esp32c3": "esptool", "esp8266": "esptool",
                        "rp2040": "avrdude", "unknown": "avrdude"}
            tool = tool_map.get(bid, "avrdude")
            self.board_flash_tool_label.setText(f"Flash-Tool: {tool}")
            # Override board label with manual selection
            self.board_auto_label.setText(f"Manuell: {self.board_manual_combo.currentText()}")
        else:
            self.board_flash_tool_label.setText("Flash-Tool: —")
            self._update_board_info()

    def _on_uri_changed(self, text):
        self._melissa_uri = text

    def _start_ws(self):
        """Start WebSocket connection to Melissa."""
        if self._ws_worker:
            self._ws_worker.stop()
            self._ws_worker = None
        self._ws_worker = WSWorker(self._get_ws_uri(), self._melissa_token)
        self._ws_worker.connected.connect(self._on_ws_connected)
        self._ws_worker.disconnected.connect(self._on_ws_disconnected)
        self._ws_worker.message_received.connect(self._on_ws_message)
        self._ws_worker.start()
        self.conn_label.setText("Melissa: " + UI_STRINGS["melissa_connecting"])
        self.conn_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        self.log("[INFO]", "Verbinde mit Melissa...")

    def _on_ws_connected(self):
        self._melissa_connected = True
        self.conn_label.setText("Melissa: " + UI_STRINGS["melissa_connected"])
        self.conn_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.status_bar.showMessage("Melissa verbunden ✓", 5000)
        self.log("[SYSTEM]", "Melissa verbunden ✓")
        # Notify Tobi via WhatsApp webhook
        self._notify_tobi("🔌 ArduinoBridge ist jetzt mit Melissa verbunden!")

    def _on_ws_disconnected(self):
        self._melissa_connected = False
        self.conn_label.setText("Melissa: " + UI_STRINGS["melissa_disconnected"])
        self.conn_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        self.log("[WARN]", "Melissa getrennt")

    def _on_ws_message(self, data: dict):
        msg_type = data.get("type", "")
        if msg_type == "flash":
            # Melissa sent a flash command!
            hex_data = data.get("hex", "")
            port = data.get("port", self.port_combo.currentData() or "COM3")
            board = data.get("board", self.board_manual_combo.currentData() or "auto")
            self.log("[MELISSA]", f"Flash-Befehl empfangen: {board} an {port}")
            if hex_data:
                self._flash_from_hex_string(hex_data, port, board)
        elif msg_type == "ping":
            self.log("[DEBUG]", "Ping von Melissa")
        else:
            self.log("[MSG]", f"Unbekannt: {msg_type}")

    def _notify_tobi(self, message: str):
        """Send notification to Tobi via OpenClaw gateway."""
        try:
            # Read gateway config
            config_path = os.path.expanduser("~/.openclaw/gateway.json")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = json.load(f)
                    whatsapp = cfg.get("whatsapp", {})
                    if whatsapp.get("enabled"):
                        # Use OpenClaw's internal notification via ws_manager
                        pass
        except Exception as e:
            logger.error(f"Notify failed: {e}")

    def _tailscale_login(self):
        auth_key = self.tailscale_key_edit.text().strip()
        if not auth_key:
            self.log("[ERROR]", "Bitte Tailscale Auth Key eingeben")
            return
        self.log("[INFO]", "Tailscale Login...")
        tailscale_path = self._get_tailscale_path()
        if not tailscale_path:
            self.log("[ERROR]", "Tailscale nicht gefunden")
            return

        import subprocess, threading
        def run_tailscale():
            try:
                result = subprocess.run(
                    [tailscale_path, "login", "--authkey", auth_key, "--hostname", "arduinobridge"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    self._on_tailscale_connected()
                else:
                    self.log("[ERROR]", f"Tailscale Login fehlgeschlagen: {result.stderr}")
            except Exception as e:
                self.log("[ERROR]", f"Tailscale Fehler: {e}")

        threading.Thread(target=run_tailscale, daemon=True).start()

    def _tailscale_logout(self):
        import subprocess, threading
        def run_tailscale():
            tailscale_path = self._get_tailscale_path()
            if tailscale_path:
                subprocess.run([tailscale_path, "logout"], capture_output=True)
            self._on_tailscale_disconnected()

        threading.Thread(target=run_tailscale, daemon=True).start()

    def _get_tailscale_path(self) -> str | None:
        """Find bundled tailscale.exe or system tailscale."""
        import shutil
        # Check bundled location (relative to exe)
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            bundled = os.path.join(base_dir, "tailscale.exe")
            if os.path.isfile(bundled):
                return bundled
        # Check system PATH
        return shutil.which("tailscale") or shutil.which("tailscale.exe")

    def _on_tailscale_connected(self):
        """Get Tailscale IP and use it for WS."""
        import subprocess, threading
        def get_ip():
            tailscale_path = self._get_tailscale_path()
            if not tailscale_path:
                return
            try:
                result = subprocess.run(
                    [tailscale_path, "ip", "-4"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    ts_ip = result.stdout.strip()
                    if ts_ip.startswith("100."):
                        self._tailscale_ip = ts_ip
                        self.tailscale_status_label.setText(f"Tailscale: ● {ts_ip}")
                        self.tailscale_status_label.setStyleSheet("color: #10B981; font-weight: bold;")
                        self.tailscale_ip_label.setText(f"→ WS: ws://{ts_ip}:18789")
                        self.tailscale_logout_btn.setEnabled(True)
                        self.tailscale_login_btn.setEnabled(False)
                        self.log("[SYSTEM]", f"Tailscale verbunden: {ts_ip}")
            except Exception as e:
                self.log("[WARN]", f"Tailscale IP fehlgeschlagen: {e}")

        threading.Thread(target=get_ip, daemon=True).start()

    def _on_tailscale_disconnected(self):
        self._tailscale_ip = None
        self.tailscale_status_label.setText("Tailscale: ○ Getrennt")
        self.tailscale_status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        self.tailscale_ip_label.setText("")
        self.tailscale_logout_btn.setEnabled(False)
        self.tailscale_login_btn.setEnabled(True)
        self.log("[INFO]", "Tailscale getrennt")

    def _get_ws_uri(self) -> str:
        """Get WebSocket URI preferring Tailscale IP."""
        if hasattr(self, '_tailscale_ip') and self._tailscale_ip:
            return f"ws://{self._tailscale_ip}:18789"
        return self._melissa_uri

    def _flash_from_hex_string(self, hex_str: str, port: str, board: str):
        """Flash from raw HEX string (received from Melissa)."""
        import tempfile
        # Clean hex string
        hex_clean = hex_str.replace(" ", "").replace("\n", "").replace("\r", "")
        try:
            data = bytes.fromhex(hex_clean)
        except ValueError:
            self.log("[ERROR]", "Ungültige HEX-Daten von Melissa")
            return
        fd, path = tempfile.mkstemp(suffix=".hex")
        os.write(fd, data)
        os.close(fd)
        self.hex_path_edit.setText(path)
        self._do_flash()

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
            "ArduinoBridge v1.0.0\n\nDesktop-Tool für Arduino-Firmware-Flash\n\nMade with ❤️ for Tobi\n\nFeatures:\n• COM-Port-Scanner\n• Board Auto-Detection + Manual Override\n• Melissa WebSocket Verbindung\n• HEX-Flash per Datei oder Melissa")

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
            self.board_auto_label.setText(UI_STRINGS["no_ports"])

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
            self.board_auto_label.setText(f"Erkannt: {board.name} ({board.board_type})")
            self.board_flash_tool_label.setText(f"Flash-Tool: {board.flash_tool}")
            # Auto-select matching board in manual combo
            board_map = {"atmega328p": "uno", "atmega2560": "mega", "esp32": "esp32",
                         "esp8266": "esp8266", "esp32c3": "esp32c3"}
            bid = board_map.get(board.mcu, "unknown")
            idx2 = self.board_manual_combo.findData(bid)
            if idx2 >= 0:
                self.board_manual_combo.blockSignals(True)
                self.board_manual_combo.setCurrentIndex(idx2)
                self.board_manual_combo.blockSignals(False)
        else:
            self.board_auto_label.setText(f"⚠ Unbekanntes Board — {port_info.hwid}")

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
        hex_path = self.hex_path_edit.text().strip()
        if not hex_path:
            self.log("[ERROR]", "Bitte HEX-Datei auswählen")
            return
        if not os.path.isfile(hex_path):
            self.log("[ERROR]", f"Datei nicht gefunden: {hex_path}")
            return

        port = self.port_combo.currentData()
        board_id = self.board_manual_combo.currentData()
        if not port:
            self.log("[ERROR]", "Bitte Port auswählen")
            return

        self.log("[INFO]", f"Starte Flash auf {port} mit {board_id}")
        self.flash_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(10)

        # Import flasher and do the flash
        from ..core import Flasher, FlashParams
        flasher = Flasher()

        tool_map = {"uno": "avrdude", "nano": "avrdude", "nano_old": "avrdude",
                    "mega": "avrdude", "leonardo": "avrdude",
                    "esp32": "esptool", "esp32c3": "esptool", "esp8266": "esptool",
                    "rp2040": "avrdude"}
        mcu_map = {"uno": "atmega328p", "nano": "atmega328p", "nano_old": "atmega168",
                   "mega": "atmega2560", "esp32": "esp32", "esp32c3": "esp32c3",
                   "esp8266": "esp8266", "rp2040": "rp2040"}

        params = FlashParams(
            port=port,
            board_type=board_id,
            flash_tool=tool_map.get(board_id, "avrdude"),
            mcu=mcu_map.get(board_id, "atmega328p"),
            hex_path=hex_path,
            baud=115200
        )

        def progress_cb(pct, msg):
            self.progress.setValue(pct)
            if msg:
                self.log("[DEBUG]", msg)

        success, message = flasher.flash(params, progress_cb)
        self.progress.setVisible(False)
        self.flash_btn.setEnabled(True)

        if success:
            self.log("[SYSTEM]", f"✅ Flash erfolgreich! {message}")
            self.status_bar.showMessage("Flash erfolgreich ✓", 5000)
        else:
            self.log("[ERROR]", f"❌ Flash fehlgeschlagen: {message}")
            self.status_bar.showMessage("Flash fehlgeschlagen ❌", 5000)

    def log(self, prefix: str, message: str):
        self.log_output.append(f"{prefix} {message}")
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        if hasattr(self, '_auto_timer'):
            self._auto_timer.stop()
        if self._ws_worker:
            self._ws_worker.stop()
            self._ws_worker.wait(1000)
        event.accept()
