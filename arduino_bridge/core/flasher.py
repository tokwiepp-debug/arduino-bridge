"""
Flash Firmware — PROJ-3
avrdude and esptool integration for flashing Arduino/ESP32 boards.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger("arduino_bridge.flasher")

@dataclass
class FlashParams:
    port: str
    board_type: str
    flash_tool: str
    mcu: str
    hex_path: str
    baud: int = 115200

class Flasher:
    def __init__(self):
        self._avrdude_path: str | None = None
        self._esptool_path: str | None = None
        self._find_tools()

    def _find_tools(self):
        """Find avrdude and esptool."""
        for tool in ["avrdude", "avrdude.exe"]:
            path = shutil.which(tool)
            if path:
                self._avrdude_path = path
                logger.info(f"avrdude gefunden: {path}")
                break
        for tool in ["esptool.py", "esptool", "esptool.exe"]:
            path = shutil.which(tool)
            if path:
                self._esptool_path = path
                logger.info(f"esptool gefunden: {path}")
                break

    def flash(self, params: FlashParams, progress_callback=None) -> tuple[bool, str]:
        """
        Flash firmware using avrdude or esptool.
        progress_callback(pct: int, message: str) is called during flashing.
        Returns (success: bool, message: str)
        """
        if not os.path.isfile(params.hex_path):
            return False, f"HEX-Datei nicht gefunden: {params.hex_path}"

        if params.flash_tool == "avrdude":
            return self._flash_avrdude(params, progress_callback)
        elif params.flash_tool == "esptool":
            return self._flash_esptool(params, progress_callback)
        else:
            return False, f"Unbekanntes Flash-Tool: {params.flash_tool}"

    def _flash_avrdude(self, params: FlashParams, cb=None) -> tuple[bool, str]:
        mcu_map = {
            "atmega328p": "m328p",
            "atmega2560": "m2560",
        }
        mcu_flag = mcu_map.get(params.mcu, "m328p")
        
        cmd = [
            self._avrdude_path or "avrdude",
            "-v", "-patmega328p", f"-C{self._avrdude_path}/../avrdude.conf",
            f"-b{params.baud}", f"-P{params.port}",
            "-Uflash:w:{params.hex_path}:i"
        ]
        
        if cb:
            cb(10, "Starte avrdude...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                if cb:
                    cb(100, "Flash erfolgreich!")
                return True, "Flash erfolgreich"
            else:
                return False, result.stderr or "avrdude Fehler"
        except subprocess.TimeoutExpired:
            return False, "Timeout nach 120s"
        except FileNotFoundError:
            return False, "avrdude nicht gefunden"

    def _flash_esptool(self, params: FlashParams, cb=None) -> tuple[bool, str]:
        cmd = [
            self._esptool_path or "esptool.py",
            "--chip", params.mcu,
            "--port", params.port,
            "--baud", str(params.baud),
            "write_flash", "0x1000", params.hex_path
        ]
        
        if cb:
            cb(10, "Starte esptool...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                if cb:
                    cb(100, "Flash erfolgreich!")
                return True, "Flash erfolgreich"
            else:
                return False, result.stderr or "esptool Fehler"
        except subprocess.TimeoutExpired:
            return False, "Timeout nach 120s"
        except FileNotFoundError:
            return False, "esptool nicht gefunden"