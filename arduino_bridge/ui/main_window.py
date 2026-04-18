"""
Main Window — ArduinoBridge mit Melissa Reverse Connection
Tool connects TO Melissa gateway as WS client, registers its IP,
then listens on port 18790 for Melissa to connect back and send commands.
"""

import logging
import os
import sys
import asyncio
import json
import socket
import threading
import time
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QLabel, QLineEdit, QProgressBar, QTextEdit, QStatusBar,
    QMenuBar, QMenu, QFileDialog, QCheckBox, QToolBar, QGroupBox, QFormLayout)
from PyQt6.QtGui import QAction

from .theme import DARK_STYLESHEET, UI_STRINGS
from ..core import PortScanner, BoardDetector

logger = logging.getLogger("arduino_bridge.main_window")

# Melissa gateway address
MELISSA_GATEWAY_URL = "ws://192.168.178.25:18789"
MELISSA_GATEWAY_USER = "admin"
MELISSA_GATEWAY_PASS = "Legitim-0208"

# Local ports
WS_SERVER_PORT = 18790
UDP_BROADCAST_PORT = 18791

# Gateway auth
AUTH_HEADER = "Basic " + ("admin:Legitim-0208".encode().hex())


class WSClientWorker(QThread):
    """Background thread: connects as WebSocket CLIENT to Melissa gateway and registers this tool."""
    connected = pyqtSignal(str)      # Emits gateway URL on success
    disconnected = pyqtSignal()
    registration_failed = pyqtSignal(str)

    def __init__(self, gateway_url: str, local_ip: str, ws_port: int = WS_SERVER_PORT):
        super().__init__()
        self.gateway_url = gateway_url
        self.local_ip = local_ip
        self.ws_port = ws_port
        self._running = True
        self.daemon = True
        self._ws = None

    def run(self):
        asyncio.new_event_loop().run_until_complete(self._run())

    async def _run(self):
        import websockets

        headers = []
        import base64
        auth_bytes = f"{MELISSA_GATEWAY_USER}:{MELISSA_GATEWAY_PASS}".encode()
        auth_b64 = base64.b64encode(auth_bytes).decode()
        headers.append(("Authorization", f"Basic {auth_b64}"))

        while self._running:
            try:
                async with websockets.connect(self.gateway_url, extra_headers=headers, max_size=16*1024*1024) as ws:
                    self._ws = ws
                    logger.info(f"Verbunden mit Melissa Gateway: {self.gateway_url}")
                    self.connected.emit(self.gateway_url)

                    # Send registration message
                    register_msg = {
                        "type": "register",
                        "tool": "arduino-bridge",
                        "ip": self.local_ip,
                        "ws_port": self.ws_port,
                        "version": "1.0.0",
                        "capabilities": ["flash"]
                    }
                    await ws.send(json.dumps(register_msg))
                    logger.info(f"Registration gesendet: {register_msg}")

                    # Keep connection alive, receive any messages from gateway
                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                            # Gateway might send pings or other messages
                            try:
                                data = json.loads(msg)
                                if data.get("type") == "pong":
                                    logger.debug("Pong empfangen")
                            except json.JSONDecodeError:
                                pass
                        except asyncio.TimeoutError:
                            # Send ping to keep alive
                            try:
                                await ws.send(json.dumps({"type": "ping"}))
                            except Exception:
                                break
            except Exception as e:
                logger.warning(f"WS Client getrennt: {e}")
                self._ws = None
                self.disconnected.emit()

            # Retry after 5 seconds
            for _ in range(50):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        if self._ws:
            try:
                asyncio.new_event_loop().run_until_complete(self._ws.close())
            except Exception:
                pass


class WSServerWorker(QThread):
    """Background thread: WebSocket SERVER on port 18790 — waits for Melissa to connect and send commands."""
    melissa_connected = pyqtSignal(str)   # Emits IP:port of connected Melissa
    melissa_disconnected = pyqtSignal()
    message_received = pyqtSignal(dict)

    def __init__(self, port: int = WS_SERVER_PORT):
        super().__init__()
        self.port = port
        self._running = True
        self.daemon = True
        self._connected_addr = None

    def run(self):
        asyncio.new_event_loop().run_until_complete(self._run_server())

    async def _run_server(self):
        import websockets

        async def handler(ws):
            self._connected_addr = ws.remote_address[0]
            addr_str = f"{self._connected_addr}:{ws.remote_address[1]}"
            logger.info(f"Melissa Command-Verbindung: {addr_str}")
            self.melissa_connected.emit(addr_str)

            try:
                async for raw_msg in ws:
                    try:
                        data = json.loads(raw_msg)
                        self.message_received.emit(data)
                    except json.JSONDecodeError:
                        pass
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self._connected_addr = None
                self.melissa_disconnected.emit()

        try:
            async with websockets.serve(handler, "0.0.0.0", self.port, max_size=16*1024*1024):
                logger.info(f"WS Server (Command) gestartet auf Port {self.port}")
                while self._running:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"WS Server Fehler: {e}")

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

        # Connection workers
        self._ws_client: WSClientWorker | None = None
        self._ws_server: WSServerWorker | None = None

        # Get local IP
        self._local_ip = self._get_local_ip()
        self._melissa_registered = False

        self._init_ui()
        self._init_menu()
        self._scan_ports()
        QTimer.singleShot(200, self._start_connections)

    def _get_local_ip(self) -> str:
        """Get local LAN IP address. Tries multiple methods."""
        # Method 1: connect to gateway (most reliable - we know it's on the LAN)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("192.168.178.25", 18789))
            ip = s.getsockname()[0]
            s.close()
            logger.info(f"Local IP detected: {ip}")
            return ip
        except Exception as e:
            logger.warning(f"Method 1 (gateway connect) failed: {e}")
        # Method 2: connect to 8.8.8.8 (fallback)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            logger.info(f"Local IP detected: {ip}")
            return ip
        except Exception as e:
            logger.warning(f"Method 2 (8.8.8.8) failed: {e}")
        # Method 3: use hostname resolution
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if not ip.startswith("127."):
                logger.info(f"Local IP detected: {ip}")
                return ip
        except Exception as e:
            logger.warning(f"Method 3 (hostname) failed: {e}")
        logger.error("Could not detect local IP - all methods failed")
        return "unbekannt"

    def _start_connections(self):
        """Start WS client (to Melissa gateway) + WS server (for commands)."""
        # Start WS server on 18790 — waits for Melissa to connect with commands
        self._ws_server = WSServerWorker(WS_SERVER_PORT)
        self._ws_server.melissa_connected.connect(self._on_melissa_connected)
        self._ws_server.melissa_disconnected.connect(self._on_melissa_disconnected)
        self._ws_server.message_received.connect(self._on_ws_message)
        self._ws_server.start()
        self.log("[INFO]", f"WS Server (Command) gestartet auf Port {WS_SERVER_PORT}")

        # Start WS client — connects TO Melissa gateway to register our IP
        self._ws_client = WSClientWorker(MELISSA_GATEWAY_URL, self._local_ip, WS_SERVER_PORT)
        self._ws_client.connected.connect(self._on_melissa_registered)
        self._ws_client.disconnected.connect(self._on_melissa_disconnected)
        self._ws_client.start()
        self.log("[INFO]", f"WS Client → Melissa Gateway: {MELISSA_GATEWAY_URL}")

    def _on_melissa_registered(self, gateway_url: str):
        self._melissa_registered = True
        self.conn_label.setText("Melissa Gateway: ✅ Registriert")
        self.conn_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.melissa_status_label.setText(f"Verbunden mit Melissa Gateway")
        self.melissa_status_label.setStyleSheet("color: #10B981;")
        self.status_bar.showMessage(f"Verbunden mit Melissa Gateway — Eigene IP: {self._local_ip}", 10000)
        self.log("[SYSTEM]", f"Bei Melissa Gateway registriert (IP: {self._local_ip}, Port: {WS_SERVER_PORT})")

    def _on_melissa_connected(self, addr: str):
        self.conn_label.setText(f"Melissa: ● Verbunden ({addr})")
        self.conn_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.status_bar.showMessage(f"Melissa Command-Verbindung: {addr}", 5000)
        self.log("[SYSTEM]", f"Melissa verbunden (Command): {addr}")

    def _on_melissa_disconnected(self):
        self._melissa_registered = False
        self.conn_label.setText("Melissa Gateway: ○ Nicht verbunden")
        self.conn_label.setStyleSheet("color: #A0A0B0; font-weight: bold;")
        self.melissa_status_label.setText("Nicht verbunden — starte neu...")
        self.melissa_status_label.setStyleSheet("color: #A0A0B0;")
        self.log("[WARN]", "Melissa getrennt — versuche neu...")

        # Restart WS client after delay
        QTimer.singleShot(5000, self._restart_client)

    def _restart_client(self):
        if self._ws_client:
            self._ws_client.stop()
            self._ws_client = None
        self._ws_client = WSClientWorker(MELISSA_GATEWAY_URL, self._local_ip, WS_SERVER_PORT)
        self._ws_client.connected.connect(self._on_melissa_registered)
        self._ws_client.disconnected.connect(self._on_melissa_disconnected)
        self._ws_client.start()
        self.log("[INFO]", "WS Client neu gestartet")

    def _on_ws_message(self, data: dict):
        msg_type = data.get("type", "")
        if msg_type == "flash":
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

    def _flash_from_hex_string(self, hex_str: str, port: str, board: str):
        """Flash from raw HEX string (received from Melissa)."""
        import tempfile
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

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # === Melissa-Verbindung Section ===
        melissa_group = QGroupBox("Melissa-Verbindung")
        melissa_layout = QFormLayout(melissa_group)

        self.conn_label = QLabel("Melissa Gateway: ○ Nicht verbunden")
        self.conn_label.setStyleSheet("color: #A0A0B0; font-weight: bold;")
        melissa_layout.addRow("Status:", self.conn_label)

        self.melissa_status_label = QLabel("Nicht verbunden")
        self.melissa_status_label.setStyleSheet("color: #A0A0B0;")
        melissa_layout.addRow("Verbindung:", self.melissa_status_label)

        self.ip_info_label = QLabel(f"Eigene IP: {self._local_ip}  |  Command-Port: {WS_SERVER_PORT}")
        self.ip_info_label.setStyleSheet("color: #A0A0B0; font-size: 9pt;")
        melissa_layout.addRow("Info:", self.ip_info_label)

        self.restart_btn = QPushButton("🔄 Neu verbinden")
        self.restart_btn.setFixedWidth(130)
        self.restart_btn.clicked.connect(self._restart_client)
        melissa_layout.addRow("", self.restart_btn)

        layout.addWidget(melissa_group)

        # === Port Scanner Toolbar ===
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

        # === Board Info + Manual Selector ===
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

        # === HEX File ===
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

        # === Flash Buttons ===
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

        # === Progress Bar ===
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # === Log ===
        layout.addWidget(QLabel(UI_STRINGS["log_label"]))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        layout.addWidget(self.log_output)

        # === Status Bar ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(UI_STRINGS["status_ready"])

    def _populate_manual_boards(self):
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
            self.board_auto_label.setText(f"Manuell: {self.board_manual_combo.currentText()}")
        else:
            self.board_flash_tool_label.setText("Flash-Tool: —")
            self._update_board_info()

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
            f"ArduinoBridge v1.0.0\n\n"
            f"Melissa Reverse Connection\n\n"
            f"• Gateway: {MELISSA_GATEWAY_URL}\n"
            f"• Command-Port: {WS_SERVER_PORT}\n"
            f"• Eigene IP: {self._local_ip}\n\n"
            "Desktop-Tool für Arduino-Firmware-Flash\n\n"
            "Made with ❤️ for Tobi")

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
        if self._ws_client:
            self._ws_client.stop()
            self._ws_client = None
        if self._ws_server:
            self._ws_server.stop()
            self._ws_server.wait(1000)
            self._ws_server = None
        event.accept()