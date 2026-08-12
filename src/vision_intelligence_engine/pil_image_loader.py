"""
Image loader using PIL (Pillow) to load various image formats.
"""

from .interfaces import ImageLoader
from .types import ImageItem, ImageType
import os
import logging

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class PILImageLoader(ImageLoader):
    """Loads images using PIL (Pillow)."""

    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError("Pillow library is required for PILImageLoader. Install it with 'pip install pillow'.")

    def load(self, source: str, **kwargs) -> ImageItem:
        """
        Load an image from a file path and return an ImageItem.

        Args:
            source: Path to the image file.
            **kwargs: Additional options (not used in this implementation).

        Returns:
            ImageItem representing the loaded image.
        """
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Image file not found: {source}")

        try:
            with Image.open(source) as img:
                # Convert to RGB if necessary (for consistency)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                # Get image data as bytes
                from io import BytesIO
                buffer = BytesIO()
                img.save(buffer, format=img.format)
                image_bytes = buffer.getvalue()

                # Determine image type from extension
                ext = os.path.splitext(source)[1].lower()
                if ext in [".jpg", ".jpeg"]:
                    image_type = ImageType.JPEG
                elif ext == ".png":
                    image_type = ImageType.PNG
                elif ext == ".webp":
                    image_type = ImageType.WEBP
                elif ext == ".bmp":
                    image_type = ImageType.BMP
                elif ext in [".tiff", ".tif"]:
                    image_type = ImageType.TIFF
                else:
                    # Default to JPEG if unknown
                    image_type = ImageType.JPEG

                # Create ImageItem
                image_item = ImageItem(
                    image_id="",  # Will be set by the store
                    image_type=image_type,
                    data=image_bytes,
                    # We'll store metadata as a dict for now, but we have ImageMetadata class
                    # We'll convert to ImageMetadata in the metadata extractor step
                )
                # We'll set the metadata in the image_item.metadata field later via the metadata extractor
                # For now, we can set it as a dict and let the metadata extractor convert it
                # But note: the ImageItem expects an ImageMetadata object for the metadata field.
                # Let's create an ImageMetadata instance from the dict.
                from .types import ImageMetadata
                image_item.metadata = ImageMetadata(
                    width=img.width,
                    height=img.height,
                    format=img.format or "",
                    mode=img.mode,
                    size=os.path.getsize(source),
                    filename=os.path.basename(source),
                )

                return image_item
        except Exception as e:
            logger.error(f"Failed to load image from {source}: {e}")
            raise

    def supports_type(self, image_type: ImageType) -> bool:
        """Check if the loader supports the given image type."""
        supported_types = {
            ImageType.JPEG,
            ImageType.PNG,
            ImageType.WEBP,
            ImageType.BMP,
            ImageType.TIFF,
        }
        return image_type in supported_types