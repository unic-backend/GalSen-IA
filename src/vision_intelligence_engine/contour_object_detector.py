"""
Contour-based object detector.
"""

from typing import List, Dict, Any
from .interfaces import ObjectDetector
from .types import ImageItem
import logging
import cv2
import numpy as np
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class ContourObjectDetector(ObjectDetector):
    """
    Detects objects using contour analysis.
    This is a simple detector that finds contours in the image after thresholding.
    """

    def __init__(self, min_area: int = 500):
        """
        Initialize the contour detector.

        Args:
            min_area: Minimum contour area to consider as an object.
        """
        self.min_area = min_area
        logger.info("Contour object detector initialized.")

    def detect_objects(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Detect objects in the image using contour detection.

        Each detection is a dictionary with keys:
            - 'label': str, the object label (we'll use "object")
            - 'confidence': float, confidence score (we'll use a fixed value)
            - 'bbox': list of [x, y, width, height] (bounding box)

        Args:
            image_item: The image to process.
            **kwargs: Additional arguments (e.g., min_area to override the instance value).

        Returns:
            List of detection dictionaries.
        """
        min_area = kwargs.get("min_area", self.min_area)
        try:
            # Load image from bytes and convert to OpenCV format
            img = Image.open(BytesIO(image_item.data))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img_array = np.array(img)
            # Convert RGB to BGR for OpenCV
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            # Convert to grayscale
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            # Apply threshold to get binary image
            _, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY_INV)
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # Filter contours by area
            detections = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > min_area:
                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(contour)
                    # We'll assign a fixed confidence based on how much the contour stands out
                    # We can use the ratio of the area to the image area as a rough confidence
                    img_area = img_array.shape[0] * img_array.shape[1]
                    confidence = min(0.9, area / img_area * 10)  # Scale to get a reasonable value
                    confidence = max(0.1, min(confidence, 0.9))  # Clamp between 0.1 and 0.9
                    detections.append({
                        "label": "object",
                        "confidence": float(confidence),
                        "bbox": [int(x), int(y), int(w), int(h)]
                    })
            return detections
        except Exception as e:
            logger.error(f"Error during object detection: {e}")
            raise