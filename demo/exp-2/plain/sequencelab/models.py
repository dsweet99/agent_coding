"""Data models for SequenceLab."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TransformMetadata:
    """Metadata linking a derived series to its source and transformation."""

    source_id: str
    operation: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "operation": self.operation,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TransformMetadata":
        return cls(
            source_id=data["source_id"],
            operation=data["operation"],
            arguments=data.get("arguments", {}),
        )


@dataclass
class Series:
    """A time-ordered numeric data series."""

    name: str
    values: List[float]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    transform_metadata: Optional[TransformMetadata] = None

    def to_dict(self) -> dict:
        """Convert series to a dictionary for serialization."""
        result = {
            "id": self.id,
            "name": self.name,
            "values": self.values,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.transform_metadata:
            result["transform_metadata"] = self.transform_metadata.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Series":
        """Create a Series from a dictionary."""
        transform_metadata = None
        if "transform_metadata" in data:
            transform_metadata = TransformMetadata.from_dict(data["transform_metadata"])
        return cls(
            id=data["id"],
            name=data["name"],
            values=data["values"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            transform_metadata=transform_metadata,
        )
