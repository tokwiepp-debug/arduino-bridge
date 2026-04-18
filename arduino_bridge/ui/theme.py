"""
Dark Theme — PROJ-4
PyQt6 dark theme with German UI strings.
"""

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1E1E2E;
    color: #E0E0E0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QPushButton {
    background-color: #7C3AED;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #6D28D9;
}
QPushButton:disabled {
    background-color: #404050;
    color: #707070;
}
QPushButton[危险] {
    background-color: #EF4444;
}
QPushButton[危险]:hover {
    background-color: #DC2626;
}
QComboBox {
    background-color: #3C3C4F;
    border: 1px solid #404050;
    padding: 4px 8px;
    border-radius: 4px;
    color: #E0E0E0;
}
QComboBox::dropDown {
    border: none;
    background-color: #3C3C4F;
}
QComboBox QAbstractItemView {
    background-color: #2A2A3E;
    color: #E0E0E0;
    selection-background-color: #7C3AED;
    border: 1px solid #404050;
}
QLineEdit, QTextEdit {
    background-color: #2A2A3E;
    border: 1px solid #404050;
    color: #E0E0E0;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #7C3AED;
}
QProgressBar {
    border: 1px solid #404050;
    border-radius: 4px;
    text-align: center;
    background-color: #2A2A3E;
    color: #E0E0E0;
}
QProgressBar::chunk {
    background-color: #7C3AED;
}
QStatusBar {
    background-color: #2A2D3E;
    color: #A0A0B0;
}
QMenuBar {
    background-color: #2A2D3E;
    color: #E0E0E0;
}
QMenuBar::item:selected {
    background-color: #3C3C4F;
}
QMenu {
    background-color: #2A2D3E;
    color: #E0E0E0;
    border: 1px solid #404050;
}
QMenu::item:selected {
    background-color: #3C3C4F;
}
QToolBar {
    background-color: #2A2D3E;
    border: none;
    spacing: 8px;
    padding: 4px;
}
"""

UI_STRINGS = {
    "app_title": "ArduinoBridge",
    "port_label": "Anschluss:",
    "port_none": "Kein Port ausgewählt",
    "refresh_btn": "🔄 Aktualisieren",
    "auto_refresh_cb": "Auto-Aktualisieren",
    "board_label": "Board:",
    "board_unknown": "Kein Board angeschlossen",
    "board_detected": "{name} (erkannt)",
    "board_unknown_port": "Unbekanntes Board an {port}",
    "flash_tool_label": "Flash-Tool: {tool}",
    "firmware_label": "Firmware:",
    "browse_btn": "Durchsuchen...",
    "flash_btn": "🔥 Flashen",
    "cancel_btn": "Abbrechen",
    "status_ready": "Bereit",
    "status_scanning": "Scanne Ports...",
    "status_flashing": "Flashen...",
    "status_success": "✅ Erfolgreich",
    "status_error": "❌ Fehlgeschlagen",
    "status_disconnected": "○ Getrennt",
    "status_connected": "● Verbunden",
    "spruts_count": "Spruts: {n} geladen",
    "menu_file": "Datei",
    "menu_exit": "Beenden",
    "menu_help": "Hilfe",
    "menu_about": "Über",
    "log_label": "Log:",
    "no_ports": "Keine Ports gefunden",
    "ports_found": "{n} Port(s) gefunden",
    "hwid_label": "HWID:",
    "select_hex": "HEX-Datei auswählen",
    "hex_filter": "HEX Files (*.hex);;All Files (*.*)",
    "melissa_connected": "● Verbunden",
    "melissa_disconnected": "○ Getrennt",
    "melissa_connecting": "⏳ Verbinde...",
}

COLORS = {
    "background": "#1E1E2E",
    "surface": "#2A2A3E",
    "input_bg": "#3C3C4F",
    "text_primary": "#E0E0E0",
    "text_secondary": "#A0A0B0",
    "accent": "#7C3AED",
    "success": "#10B981",
    "error": "#EF4444",
    "border": "#404050",
}
