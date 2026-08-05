"""
Factory for creating image loaders based on file extension or MIME type.
"""

from typing import Dict, Type, Optional
from .interfaces import ImageLoader
from .pil_image_loader import PILImageLoader
from .types import ImageType


class ImageLoaderFactory:
    """Factory that creates the appropriate image loader based on file extension."""

    def __init__(self):
        self._loaders: Dict[str, Type[ImageLoader]] = {}
        self._register_default_loaders()

    def _register_default_loaders(self) -> None:
        """Register the default image loaders."""
        # We'll use the PILImageLoader for all supported formats
        pil_loader = PILImageLoader()
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"]:
            self._loaders[ext] = pil_loader.__class__

    def register_loader(self, extension: str, loader_class: Type[ImageLoader]) -> None:
        """Register a loader for a specific file extension."""
        self._loaders[extension.lower()] = loader_class

    def get_loader_for_file(self, file_path: str) -> Optional[ImageLoader]:
        """Get a loader instance for the given file path based on its extension."""
        import os
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        loader_class = self._loaders.get(ext)
        if loader_class:
            return loader_class()
        return None

    def get_loader_for_type(self, image_type: ImageType) -> Optional[ImageLoader]:
        """Get a loader instance for the given image type."""
        # Map ImageType to extensions
        extension_map = {
            ImageType.JPEG: [".jpg", ".jpeg"],
            ImageType.PNG: [".png"],
            ImageType.WEBP: [".webp"],
            ImageType.BMP: [".bmp"],
            ImageType.TIFF: [".tiff", ".tif"],
        }
        extensions = extension_map.get(image_type, [])
        for ext in extensions:
            if ext in self._loaders:
                return self._loaders[ext]()
        return None