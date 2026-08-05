"""
Image metadata extraction components for the Vision Intelligence Engine.
"""

from typing import Dict, Any
from .interfaces import ImageMetadataExtractor
from .types import ImageItem
import logging
import os
from datetime import datetime

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class PILImageMetadataExtractor(ImageMetadataExtractor):
    """
    Extracts metadata from images using Pillow.
    """

    def extract_metadata(self, image_item: ImageItem) -> Dict[str, Any]:
        """
        Extract metadata from the image.

        Args:
            image_item: The image to extract metadata from.

        Returns:
            A dictionary containing metadata.
        """
        if not PIL_AVAILABLE:
            logger.warning("Pillow is not available. Returning basic metadata from image_item if available.")
            # Fallback to basic metadata from the image_item
            meta = image_item.metadata
            return {
                "width": meta.width,
                "height": meta.height,
                "format": meta.format,
                "mode": meta.mode,
                "size": meta.size,
                "created": meta.created.isoformat() if meta.created else None,
                "modified": meta.modified.isoformat() if meta.modified else None,
                "filename": meta.filename,
            }

        from io import BytesIO
        try:
            img = Image.open(BytesIO(image_item.data))
        except Exception as e:
            logger.error(f"Failed to open image data for metadata extraction: {e}")
            # Return basic metadata from the image_item if available
            meta = image_item.metadata
            return {
                "width": meta.width,
                "height": meta.height,
                "format": meta.format,
                "mode": meta.mode,
                "size": meta.size,
                "created": meta.created.isoformat() if meta.created else None,
                "modified": meta.modified.isoformat() if meta.modified else None,
                "filename": meta.filename,
            }

        # Basic image info
        width, height = img.size
        format = img.format
        mode = img.mode

        # Get EXIF data
        exif_data = {}
        if hasattr(img, '_getexif') and img._getexif() is not None:
            exif = img._getexif()
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_data[tag] = value

        # Prepare metadata dict
        metadata = {
            "width": width,
            "height": height,
            "format": format,
            "mode": mode,
            "exif": exif_data,
        }

        # If we have file path in the original metadata, we can add file stats
        if image_item.metadata.filename:
            try:
                stat = os.stat(image_item.metadata.filename)
                metadata.update({
                    "file_size": stat.st_size,
                    "file_created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "file_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except (OSError, FileNotFoundError):
                pass

        return metadata