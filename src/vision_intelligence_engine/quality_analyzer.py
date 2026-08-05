"""
Quality analyzer for assessing image quality (blur, exposure, noise).
"""

from typing import Dict, Any
from .interfaces import QualityAnalyzer
from .types import ImageItem
import logging
import numpy as np
import cv2
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class SimpleQualityAnalyzer(QualityAnalyzer):
    """
    Analyzes image quality using simple metrics.
    """

    def analyze_quality(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the quality of the image and return a dictionary of quality metrics.

        The returned dictionary includes:
            - 'blur_score': variance of the Laplacian (higher means less blur)
            - 'exposure_score': a measure of how well-exposed the image is (0 to 1, 0.5 is ideal)
            - 'noise_estimate': estimated noise level (standard deviation of high-frequency components)

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments (not used in this implementation).

        Returns:
            Dictionary of quality metrics.
        """
        try:
            # Load image from bytes
            img = Image.open(BytesIO(image_item.data))
            # Convert to grayscale for some analyses
            if img.mode != "L":
                gray_img = img.convert("L")
            else:
                gray_img = img
            # Convert to numpy array
            img_array = np.array(gray_img)
            # Ensure it's uint8
            if img_array.dtype != np.uint8:
                img_array = img_array.astype(np.uint8)

            # Blur detection using variance of Laplacian
            laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
            blur_score = np.var(laplacian)

            # Exposure: we'll compute the histogram and see how close it is to uniform
            hist = cv2.calcHist([img_array], [0], None, [256], [0, 256])
            hist = hist.flatten() / np.sum(hist)  # normalize
            # Entropy of the histogram (higher entropy means more spread out, which is better for exposure)
            # Avoid log(0)
            epsilon = 1e-10
            entropy = -np.sum(hist * np.log(hist + epsilon))
            # Normalize entropy by max possible entropy (log(256))
            max_entropy = np.log(256)
            exposure_score = entropy / max_entropy  # 1.0 is uniform, 0 is all in one bin

            # Noise estimation: we'll use a simple method - subtract a blurred version and compute std of the difference
            blurred = cv2.GaussianBlur(img_array, (5, 5), 0)
            noise = img_array.astype(np.float32) - blurred.astype(np.float32)
            noise_estimate = np.std(noise)

            return {
                "blur_score": float(blur_score),
                "exposure_score": float(exposure_score),
                "noise_estimate": float(noise_estimate)
            }
        except Exception as e:
            logger.error(f"Error during quality analysis: {e}")
            raise