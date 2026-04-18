"""
Flash Firmware — PROJ-4
avrdude and esptool integration for flashing Arduino/ESP32 boards.
Proper subprocess handling with non-blocking progress callbacks.
"""

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable

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

    def flash(self, params: FlashParams, progress_callback: Callable[[int, str], None] | None = None) -> tuple[bool, str]:
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

    def _flash_avrdude(self, params: FlashParams, cb: Callable[[int, str], None] | None = None) -> tuple[bool, str]:
        mcu_map = {
            "atmega328p": "m328p",
            "atmega2560": "m2560",
            "atmega168": "m168",
        }
        mcu_flag = mcu_map.get(params.mcu, "m328p")

        avrdude_conf = "/etc/avrdude.conf"
        if not os.path.exists(avrdude_conf):
            avrdude_conf = "/usr/local/etc/avrdude.conf"

        cmd = [
            self._avrdude_path or "avrdude",
            "-v", "-patmega328p", f"-C{avrdude_conf}",
            f"-b{params.baud}", f"-P{params.port}",
            "-Uflash:w:{params.hex_path}:i"
        ]

        if cb:
            cb(10, "Starte avrdude...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                if cb:
                    cb(100, "Flash erfolgreich!")
                return True, "Flash erfolgreich"
            else:
                error_msg = result.stderr or "avrdude Fehler"
                if cb:
                    cb(0, f"Fehler: {error_msg}")
                return False, error_msg
        except subprocess.TimeoutExpired:
            if cb:
                cb(0, "Timeout nach 120s")
            return False, "Timeout nach 120s"
        except FileNotFoundError:
            if cb:
                cb(0, "avrdude nicht gefunden")
            return False, "avrdude nicht gefunden"

    def _flash_esptool(self, params: FlashParams, cb: Callable[[int, str], None] | None = None) -> tuple[bool, str]:
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                if cb:
                    cb(100, "Flash erfolgreich!")
                return True, "Flash erfolgreich"
            else:
                error_msg = result.stderr or "esptool Fehler"
                if cb:
                    cb(0, f"Fehler: {error_msg}")
                return False, error_msg
        except subprocess.TimeoutExpired:
            if cb:
                cb(0, "Timeout nach 120s")
            return False, "Timeout nach 120s"
        except FileNotFoundError:
            if cb:
                cb(0, "esptool nicht gefunden")
            return False, "esptool nicht gefunden"

    def flash_async(self, params: FlashParams, progress_callback: Callable[[int, str], None] | None = None, done_callback: Callable[[bool, str], None] | None = None):
        """
        Flash firmware in a background thread with callbacks.
        done_callback(success: bool, message: str) is called when done.
        """
        def run():
            success, message = self.flash(params, progress_callback)
            if done_callback:
                done_callback(success, message)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t
