"""Local JSON storage for SequenceLab data."""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from sequencelab.models import Series

DEFAULT_DATA_DIR = Path.home() / ".sequencelab"
DATA_FILE = "series.json"


class SeriesStore:
    """Manages persistence of Series objects to local JSON storage."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_file = self.data_dir / DATA_FILE
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> Dict[str, dict]:
        """Load all series data from disk."""
        if not self.data_file.exists():
            return {}
        with open(self.data_file, "r") as f:
            return json.load(f)

    def _save_all(self, data: Dict[str, dict]) -> None:
        """Save all series data to disk."""
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, series: Series) -> Series:
        """Add a new series to storage."""
        data = self._load_all()
        data[series.id] = series.to_dict()
        self._save_all(data)
        return series

    def get(self, series_id: str) -> Optional[Series]:
        """Get a series by ID."""
        data = self._load_all()
        if series_id not in data:
            return None
        return Series.from_dict(data[series_id])

    def get_by_name(self, name: str) -> Optional[Series]:
        """Get a series by name."""
        data = self._load_all()
        for series_data in data.values():
            if series_data["name"] == name:
                return Series.from_dict(series_data)
        return None

    def list_all(self) -> list[Series]:
        """List all series."""
        data = self._load_all()
        return [Series.from_dict(s) for s in data.values()]

    def update(self, series: Series) -> Series:
        """Update an existing series."""
        data = self._load_all()
        if series.id not in data:
            raise KeyError(f"Series with id '{series.id}' not found")
        data[series.id] = series.to_dict()
        self._save_all(data)
        return series

    def delete(self, series_id: str) -> bool:
        """Delete a series by ID. Returns True if deleted, False if not found."""
        data = self._load_all()
        if series_id not in data:
            return False
        del data[series_id]
        self._save_all(data)
        return True

    def find(self, identifier: str) -> Optional[Series]:
        """Find a series by ID or name."""
        series = self.get(identifier)
        if series:
            return series
        return self.get_by_name(identifier)
