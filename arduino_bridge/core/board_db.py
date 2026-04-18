"""
Board Database — PROJ-2
Known boards with VID/PID, names, and flash parameters.
"""

from dataclasses import dataclass
import json
import os

@dataclass
class BoardInfo:
    name: str           # "Arduino UNO"
    vid: int            # 0x2341
    pid: int            # 0x0043
    board_type: str     # "AVR" | "ESP32" | "ESP8266"
    flash_tool: str     # "avrdude" | "esptool"
    default_baud: int   # 115200
    mcu: str            # "atmega328p"

DEFAULT_BOARDS = [
    {"name": "Arduino UNO", "vid": 0x2341, "pid": 0x0043, "board_type": "AVR", "flash_tool": "avrdude", "default_baud": 115200, "mcu": "atmega328p"},
    {"name": "Arduino Nano (Old)", "vid": 0x2341, "pid": 0x0010, "board_type": "AVR", "flash_tool": "avrdude", "default_baud": 57600, "mcu": "atmega328p"},
    {"name": "Arduino Nano (CH340)", "vid": 0x1A86, "pid": 0x7523, "board_type": "AVR", "flash_tool": "avrdude", "default_baud": 115200, "mcu": "atmega328p"},
    {"name": "Arduino Mega 2560", "vid": 0x2341, "pid": 0x0010, "board_type": "AVR", "flash_tool": "avrdude", "default_baud": 115200, "mcu": "atmega2560"},
    {"name": "ESP32 DevKit", "vid": 0x10C4, "pid": 0xEA60, "board_type": "ESP32", "flash_tool": "esptool", "default_baud": 921600, "mcu": "esp32"},
    {"name": "ESP32-C3", "vid": 0x303A, "pid": 0x0001, "board_type": "ESP32-C3", "flash_tool": "esptool", "default_baud": 921600, "mcu": "esp32c3"},
    {"name": "ESP8266 (NodeMCU)", "vid": 0x1A86, "pid": 0x7523, "board_type": "ESP8266", "flash_tool": "esptool", "default_baud": 115200, "mcu": "esp8266"},
]

class BoardDatabase:
    def __init__(self, db_path: str | None = None):
        self.boards: list[BoardInfo] = []
        if db_path and os.path.isfile(db_path):
            with open(db_path) as f:
                data = json.load(f)
                for b in data.get("boards", []):
                    self.boards.append(BoardInfo(
                        name=b["name"],
                        vid=int(b["vid"], 16) if isinstance(b["vid"], str) else b["vid"],
                        pid=int(b["pid"], 16) if isinstance(b["pid"], str) else b["pid"],
                        board_type=b["board_type"],
                        flash_tool=b["flash_tool"],
                        default_baud=b["default_baud"],
                        mcu=b.get("mcu", ""),
                    ))
        # Always add defaults
        for b in DEFAULT_BOARDS:
            if not any(board.vid == b["vid"] and board.pid == b["pid"] for board in self.boards):
                self.boards.append(BoardInfo(**b))

    def find(self, vid: int, pid: int) -> BoardInfo | None:
        for board in self.boards:
            if board.vid == vid and board.pid == pid:
                return board
        return None

    def find_by_hwid(self, hwid: str) -> BoardInfo | None:
        """Extract VID/PID from HWID string like USB\\VID_0403&PID_6001."""
        hwid_upper = hwid.upper()
        vid_str = None
        pid_str = None
        if "VID_" in hwid_upper:
            vid_start = hwid_upper.index("VID_") + 4
            vid_end = hwid_upper.index("&", vid_start) if "&" in hwid_upper[vid_start:] else vid_start + 4
            vid_str = hwid_upper[vid_start:vid_end]
        if "PID_" in hwid_upper:
            pid_start = hwid_upper.index("PID_") + 4
            pid_end = hwid_upper.index("\\", pid_start) if "\\" in hwid_upper[pid_start:] else pid_start + 4
            pid_str = hwid_upper[pid_start:pid_end]
        if vid_str and pid_str:
            try:
                return self.find(int(vid_str, 16), int(pid_str, 16))
            except ValueError:
                pass
        return None
