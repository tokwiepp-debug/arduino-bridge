"""
WebSocket AI Client — PROJ-5
Connects to Melissa (OpenClaw) via WebSocket for remote commands.
"""

import asyncio
import json
import logging
import os
from typing import Callable

logger = logging.getLogger("arduino_bridge.websocket_client")

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

class WSClient:
    """
    WebSocket client that connects to Melissa gateway.
    Supports: ping, get_status, flash command, list_ports.
    """

    def __init__(self, uri: str = "ws://localhost:18789", token: str | None = None):
        self.uri = uri
        self.token = token
        self._connected = False
        self._ws = None
        self._on_message: Callable[[dict], None] | None = None
        self._on_connect: Callable[[], None] | None = None
        self._on_disconnect: Callable[[], None] | None = None

    def set_callbacks(self, on_message=None, on_connect=None, on_disconnect=None):
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    async def connect(self):
        if not HAS_WEBSOCKETS:
            logger.error("websockets library nicht installiert")
            return False
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._ws = await websockets.connect(self.uri, extra_headers=headers)
            self._connected = True
            logger.info(f"Verbunden mit {self.uri}")
            if self._on_connect:
                self._on_connect()
            await self._listen()
        except Exception as e:
            logger.error(f"Verbindungsfehler: {e}")
            self._connected = False
            if self._on_disconnect:
                self._on_disconnect()

    async def _listen(self):
        """Listen for incoming messages."""
        async for msg in self._ws:
            try:
                data = json.loads(msg)
                logger.debug(f"WS Nachricht: {data.get('type', '?')}")
                if self._on_message:
                    self._on_message(data)
            except json.JSONDecodeError:
                logger.warning(f"Ungültige JSON: {msg}")

    async def send(self, data: dict):
        """Send a message to Melissa."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps(data))

    async def send_ping(self):
        await self.send({"type": "ping"})

    def close(self):
        self._connected = False
        if self._ws:
            asyncio.run(self._ws.close())

class WsManager:
    """Manages WebSocket connection for the main window."""
    def __init__(self, uri: str = "ws://localhost:18789"):
        self.uri = uri
        self.token = os.environ.get("OPENCLAW_TOKEN", "")
        self.ws = WSClient(uri=self.uri, token=self.token or None)
        self._loop = None

    def start(self):
        """Start the WebSocket in a background thread."""
        import threading
        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.ws.connect())
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def is_connected(self) -> bool:
        return self.ws._connected
