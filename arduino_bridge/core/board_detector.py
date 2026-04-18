"""
Board Detector — PROJ-2
Combines PortScanner + BoardDatabase for auto-detection.
"""

import logging
from .port_scanner import PortScanner, PortInfo
from .board_db import BoardDatabase, BoardInfo

logger = logging.getLogger("arduino_bridge.board_detector")

class BoardDetector:
    def __init__(self, db_path: str | None = None):
        self.scanner = PortScanner()
        self.db = BoardDatabase(db_path)

    def detect(self, port_info: PortInfo) -> BoardInfo | None:
        """Detect board type from a PortInfo object."""
        board = self.db.find_by_hwid(port_info.hwid)
        if board:
            logger.info(f"Board erkannt: {board.name} an {port_info.name}")
        else:
            logger.info(f"Unbekanntes Board an {port_info.name}: {port_info.hwid}")
        return board

    def detect_from_port_name(self, port_name: str) -> tuple[PortInfo | None, BoardInfo | None]:
        """Scan all ports and return the one matching port_name."""
        for port in self.scanner.scan():
            if port.name == port_name:
                board = self.detect(port)
                return port, board
        return None, None
