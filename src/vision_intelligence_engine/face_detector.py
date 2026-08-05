"""
Face detector that returns empty list (placeholder).
"""

from typing import List, Dict, Any
from .interfaces import FaceDetector
from .types import ImageItem
import logging

logger = logging.getLogger(__name__)


class HaarCascadeFaceDetector(FaceDetector):
    """
    Placeholder face detector that returns an empty list.
    This is used because the OpenCV CascadeClassifier may not be available in the current environment.
    """

    def __init__(self):
        """Initialize the face detector."""
        logger.info("Face detector initialized (placeholder).")

    def detect_faces(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Detect faces in the image and return a list of face detections.

        Always returns an empty list (no faces detected).

        Args:
            image_item: The image to process.
            **kwargs: Additional arguments (ignored).

        Returns:
            Empty list of face detections.
        """
        # Return empty list - no faces detected
        return []