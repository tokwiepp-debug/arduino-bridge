"""
COM-Port-Scanner — PROJ-1
Uses pyserial to enumerate and monitor COM ports.
"""

import logging
from typing import NamedTuple
import serial.tools.list_ports

logger = logging.getLogger("arduino_bridge.port_scanner")

class PortInfo(NamedTuple):
    name: str          # "COM3"
    description: str   # "USB Serial Port"
    hwid: str          # "USB\\VID_0403&PID_6001"
    vid: int           # 0x0403
    pid: int           # 0x6001
    in_use: bool       # True if port appears to be open

class PortScanner:
    def scan(self) -> list[PortInfo]:
        """Return all available COM ports."""
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            vid = p.vid or 0
            pid = p.pid or 0
            hwid = p.hwid or ""
            in_use = "IN USE" in hwid.upper() if hwid else False
            result.append(PortInfo(
                name=p.device,
                description=p.description or "Unbekannt",
                hwid=hwid,
                vid=vid,
                pid=pid,
                in_use=in_use,
            ))
        logger.info(f"{len(result)} Port(s) gefunden")
        return result

    def scan_available(self) -> list[PortInfo]:
        """Return ports that are not in use."""
        return [p for p in self.scan() if not p.in_use]
