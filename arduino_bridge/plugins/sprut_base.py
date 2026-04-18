"""
Base class for all Spruts — PROJ-6
"""

from abc import ABC, abstractmethod

class SprutBase(ABC):
    """
    Base class that all Sprut widgets must inherit from.
    """
    def __init__(self, manifest, hull_api=None):
        self.manifest = manifest
        self.hull_api = hull_api

    @abstractmethod
    def get_widget(self):
        """Return the QWidget for this Sprut."""
        pass

    def on_board_connected(self, board_info):
        """Called when a board is connected."""
        pass

    def on_board_disconnected(self, port_name):
        """Called when a board is disconnected."""
        pass

    def on_flash_started(self, port, board):
        """Called when flashing starts."""
        pass

    def on_flash_complete(self, success, message):
        """Called when flashing completes."""
        pass
