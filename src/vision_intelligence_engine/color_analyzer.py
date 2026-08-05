"""
Color analyzer for extracting color statistics from images.
"""

from typing import Dict, Any
from .interfaces import ColorAnalyzer
from .types import ImageItem
import logging
import numpy as np
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class SimpleColorAnalyzer(ColorAnalyzer):
    """
    Analyzes colors in an image using basic statistics and histogram methods.
    """

    def analyze_colors(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the colors in the image and return a dictionary of color statistics.

        The returned dictionary includes:
            - 'mean_rgb': tuple of (mean_r, mean_g, mean_b)
            - 'std_rgb': tuple of (std_r, std_g, std_b)
            - 'dominant_color': tuple of (r, g, b) of the most common color
            - 'color_histograms': dict with 'r', 'g', 'b' keys, each being a list of bin counts
            - 'unique_colors_count': approximate number of unique colors (based on quantization)

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments (e.g., 'bins' for histogram bins, default 32).

        Returns:
            Dictionary of color statistics.
        """
        bins = kwargs.get("bins", 32)
        try:
            # Load image from bytes
            img = Image.open(BytesIO(image_item.data))
            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")
            # Convert to numpy array
            img_array = np.array(img)
            # Shape: (height, width, 3)

            # Calculate mean and std per channel
            mean_rgb = tuple(np.mean(img_array, axis=(0, 1)))
            std_rgb = tuple(np.std(img_array, axis=(0, 1)))

            # Flatten the array to a list of pixels
            pixels = img_array.reshape(-1, 3)

            # Compute histogram for each channel
            hist_r, bins_r = np.histogram(img_array[:, :, 0], bins=bins, range=(0, 256))
            hist_g, bins_g = np.histogram(img_array[:, :, 1], bins=bins, range=(0, 256))
            hist_b, bins_b = np.histogram(img_array[:, :, 2], bins=bins, range=(0, 256))

            # Find the dominant color (the color of the bin with the highest count across all channels combined?)
            # We'll do a simple approach: for each channel, find the bin with max count and take the bin center.
            # Then combine to get a dominant color.
            def get_bin_center(hist, bins_array):
                max_idx = np.argmax(hist)
                return (bins_array[max_idx] + bins_array[max_idx + 1]) / 2

            dominant_r = get_bin_center(hist_r, bins_r)
            dominant_g = get_bin_center(hist_g, bins_g)
            dominant_b = get_bin_center(hist_b, bins_b)
            dominant_color = (int(dominant_r), int(dominant_g), int(dominant_b))

            # Approximate unique colors by quantizing each channel to, say, 64 levels and counting unique combinations
            quant_factor = 4  # 256/4 = 64 levels per channel
            quantized = (pixels // quant_factor) * quant_factor
            unique_colors = np.unique(quantized, axis=0)
            unique_colors_count = len(unique_colors)

            return {
                "mean_rgb": tuple(float(x) for x in mean_rgb),
                "std_rgb": tuple(float(x) for x in std_rgb),
                "dominant_color": list(dominant_color),  # JSON serializable
                "color_histograms": {
                    "r": [int(x) for x in hist_r],
                    "g": [int(x) for x in hist_g],
                    "b": [int(x) for x in hist_b]
                },
                "unique_colors_count": int(unique_colors_count)
            }
        except Exception as e:
            logger.error(f"Error during color analysis: {e}")
            raise