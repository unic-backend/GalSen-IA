"""
Types for the Vision Intelligence Engine.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import datetime


class ImageType(Enum):
    JPEG = "jpeg"
    JPG = "jpg"
    PNG = "png"
    WEBP = "webp"
    BMP = "bmp"
    TIFF = "tiff"


class ImageStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ImageMetadata:
    width: int = 0
    height: int = 0
    format: str = ""
    mode: str = ""
    size: int = 0
    created: Optional[datetime.datetime] = None
    modified: Optional[datetime.datetime] = None
    filename: str = ""
    # Additional metadata can be added as needed


@dataclass
class ImageItem:
    image_id: str = ""
    image_type: ImageType = ImageType.JPEG
    data: bytes = b""  # Raw image data
    metadata: ImageMetadata = field(default_factory=ImageMetadata)
    status: ImageStatus = ImageStatus.PENDING
    # Additional fields for analysis results will be stored in a separate structure or in metadata?
    # For simplicity, we can store analysis results in a dictionary in metadata or in a separate attribute.
    # Let's add an analysis dictionary.
    analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "image_type": self.image_type.value,
            "data": self.data.hex() if self.data else "",  # Store as hex string for simplicity
            "metadata": {
                "width": self.metadata.width,
                "height": self.metadata.height,
                "format": self.metadata.format,
                "mode": self.metadata.mode,
                "size": self.metadata.size,
                "created": self.metadata.created.isoformat() if self.metadata.created else None,
                "modified": self.metadata.modified.isoformat() if self.metadata.modified else None,
                "filename": self.metadata.filename,
            },
            "status": self.status.value,
            "analysis": self.analysis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageItem":
        metadata_dict = data.get("metadata", {})
        metadata = ImageMetadata(
            width=metadata_dict.get("width", 0),
            height=metadata_dict.get("height", 0),
            format=metadata_dict.get("format", ""),
            mode=metadata_dict.get("mode", ""),
            size=metadata_dict.get("size", 0),
            created=datetime.datetime.fromisoformat(metadata_dict["created"]) if metadata_dict.get("created") else None,
            modified=datetime.datetime.fromisoformat(metadata_dict["modified"]) if metadata_dict.get("modified") else None,
            filename=metadata_dict.get("filename", ""),
        )
        return cls(
            image_id=data.get("image_id", ""),
            image_type=ImageType(data.get("image_type", ImageType.JPEG.value)),
            data=bytes.fromhex(data.get("data", "")) if data.get("data") else b"",
            metadata=metadata,
            status=ImageStatus(data.get("status", ImageStatus.PENDING.value)),
            analysis=data.get("analysis", {}),
        )