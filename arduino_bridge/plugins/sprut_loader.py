"""
Sprut Loader — PROJ-6
Plugin system for ArduinoBridge. Loads Spruts from spruts/ directory.
"""

import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger("arduino_bridge.sprut_loader")

class SprutManifest:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.parent.name
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.id = data.get("id", path.parent.name)
        self.name = data.get("name", self.id)
        self.version = data.get("version", "1.0.0")
        self.author = data.get("author", "unknown")
        self.description = data.get("description", "")
        self.entry = data.get("entry", "sprut.py:SprutWidget")
        self.enabled = data.get("enabled_by_default", True)

class SprutLoader:
    """
    Discovers and loads Spruts from the spruts/ directory.
    """
    def __init__(self, spruts_dir: str = "spruts"):
        self.spruts_dir = Path(spruts_dir)
        self.spruts_dir.mkdir(exist_ok=True)
        self._loaded: Dict[str, SprutManifest] = {}
        self._instances: Dict[str, object] = {}

    def scan(self) -> list[SprutManifest]:
        """Find all Spruts by scanning for manifest.json files."""
        found = []
        if not self.spruts_dir.exists():
            logger.warning(f"Spruts-Verzeichnis nicht gefunden: {self.spruts_dir}")
            return found
        for item in self.spruts_dir.iterdir():
            if not item.is_dir():
                continue
            manifest_path = item / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = SprutManifest(manifest_path)
                found.append(manifest)
                logger.info(f"Sprut gefunden: {manifest.id} v{manifest.version}")
            except Exception as e:
                logger.error(f"Fehler beim Laden von {manifest_path}: {e}")
        return found

    def load_sprut(self, manifest: SprutManifest) -> bool:
        """Load and instantiate a Sprut."""
        if manifest.id in self._instances:
            return True
        sprut_path = manifest.path.parent / "sprut.py"
        if not sprut_path.exists():
            logger.error(f"Sprut-Datei fehlt: {sprut_path}")
            return False
        try:
            spec = importlib.util.spec_from_file_location(manifest.id, sprut_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            entry_parts = manifest.entry.split(":")
            cls_name = entry_parts[1] if len(entry_parts) > 1 else "SprutWidget"
            cls = getattr(module, cls_name, None)
            if cls is None:
                logger.error(f"Klasse {cls_name} nicht gefunden in {sprut_path}")
                return False
            instance = cls(manifest=manifest)
            self._instances[manifest.id] = instance
            self._loaded[manifest.id] = manifest
            logger.info(f"Sprut geladen: {manifest.id}")
            return True
        except Exception as e:
            logger.exception(f"Fehler beim Laden von {manifest.id}: {e}")
            return False

    def get_loaded(self) -> Dict[str, SprutManifest]:
        return self._loaded

    def get_instance(self, sprut_id: str):
        return self._instances.get(sprut_id)
