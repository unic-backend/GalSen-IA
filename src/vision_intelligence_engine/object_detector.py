"""
Object detector using contour detection.
"""

from typing import List, Dict, Any
from .interfaces import ObjectDetector
from .types import ImageItem
import logging
import numpy as np
import cv2
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)


class ContourObjectDetector(ObjectDetector):
    """
    Detects objects using edge detection and contour finding.
    Each contour is considered an object.
    This is a simple detector for demonstration purposes.
    """

    def __init__(self, min_area: int = 500):
        """
        Initialize the detector.

        Args:
            min_area: Minimum contour area to consider as an object.
        """
        self.min_area = min_area

    def detect_objects(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Detect objects in the image using contour detection.

        Each detection is a dictionary with keys:
            - 'label': str, always "object" for this detector
            - 'confidence': float, a measure of how likely it is an object (based on area)
            - 'bbox': list of [x, y, width, height] (bounding box)

        Args:
            image_item: The image to process.
            **kwargs: Additional arguments (e.g., min_area to override).

        Returns:
            List of detection dictionaries.
        """
        min_area = kwargs.get("min_area", self.min_area)
        try:
            # Load image from bytes
            img = Image.open(BytesIO(image_item.data))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img_array = np.array(img)
            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            # Detect edges using Canny
            edges = cv2.Canny(blurred, 50, 150)
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # Filter contours by area
            detections = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                # Confidence based on area relative to image area? We'll use a simple normalization
                # We'll set confidence to min(1.0, area / (image_area * 0.5)) but cap at 1.0
                image_area = img_array.shape[0] * img_array.shape[1]
                confidence = min(1.0, area / (image_area * 0.5)) if image_area > 0 else 0.5
                detections.append({
                    "label": "object",
                    "confidence": float(confidence),
                    "bbox": [int(x), int(y), int(w), int(h)]
                })
            return detections
        except Exception as e:
            logger.error(f"Error during object detection: {e}")
            return []