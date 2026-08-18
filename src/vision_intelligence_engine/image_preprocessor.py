"""
Image preprocessing components for the Vision Intelligence Engine.
"""

from typing import Optional, Tuple
from .interfaces import ImagePreprocessor
from .types import ImageItem
import logging
import numpy as np
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class SimpleImagePreprocessor(ImagePreprocessor):
    """
    A simple image preprocessor that resizes and normalizes images.
    """

    def __init__(self, target_size: Optional[Tuple[int, int]] = None, normalize: bool = True):
        """
        Initialize the preprocessor.

        Args:
            target_size: Tuple (width, height) to resize the image. If None, no resizing.
            normalize: If True, normalize pixel values to [0, 1] float32.
        """
        try:
            # Importés pour éprouver leur disponibilité, pas pour être utilisés ici.
            from PIL import Image  # noqa: F401
            import numpy as np  # noqa: F401
            self.PIL_AVAILABLE = True
            self.np_AVAILABLE = True
        except ImportError:
            self.PIL_AVAILABLE = False
            self.np_AVAILABLE = False
            raise ImportError("Pillow and numpy are required for SimpleImagePreprocessor. Install with 'pip install pillow numpy'.")
        self.target_size = target_size
        self.normalize = normalize

    def preprocess(self, image_item: ImageItem, **kwargs) -> ImageItem:
        """
        Preprocess the image by resizing and/or normalizing.

        Args:
            image_item: The input image.
            **kwargs: Can override target_size and normalize.

        Returns:
            A new ImageItem with preprocessed image data.
        """
        target_size = kwargs.get("target_size", self.target_size)
        normalize = kwargs.get("normalize", self.normalize)

        # Load image from bytes
        try:
            img = Image.open(BytesIO(image_item.data))
        except Exception as e:
            logger.error(f"Failed to open image data: {e}")
            raise

        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")

        original_width, original_height = img.size

        # Resize if specified
        if target_size is not None:
            img = img.resize(target_size, Image.Resampling.LANCZOS)

        # Convert to numpy array
        img_array = np.array(img)

        # Normalize if requested
        if normalize:
            # Convert to float32 and scale to [0, 1]
            img_array = img_array.astype(np.float32) / 255.0

        # Convert back to PIL Image to save as bytes
        if normalize:
            # Convert back to uint8 [0, 255] for saving
            img_array = (img_array * 255).astype(np.uint8)
        processed_img = Image.fromarray(img_array)

        # Save to bytes
        buffer = BytesIO()
        # Use the original format if possible, otherwise default to PNG
        format_to_use = image_item.image_type.value.upper()
        if format_to_use == "JPG":
            format_to_use = "JPEG"
        try:
            processed_img.save(buffer, format=format_to_use)
        except ValueError:
            # Fallback to PNG if the format is not supported for saving
            processed_img.save(buffer, format="PNG")
            format_to_use = "PNG"
        processed_bytes = buffer.getvalue()

        # Create a new ImageItem with the processed data
        from .types import ImageMetadata
        processed_item = ImageItem(
            image_id=image_item.image_id,
            image_type=image_item.image_type,
            data=processed_bytes,
            metadata=ImageMetadata(
                width=img.width,
                height=img.height,
                format=img.format,
                mode=img.mode,
                size=len(processed_bytes),
                filename=image_item.metadata.filename
            ),
            status=image_item.status,
            analysis=image_item.analysis.copy() if hasattr(image_item, 'analysis') else {}
        )

        return processed_item