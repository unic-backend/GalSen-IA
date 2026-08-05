"""
Scene analyzer that uses object detection and color analysis to describe a scene.
"""

from typing import Dict, Any
from .interfaces import SceneAnalyzer, ObjectDetector, ColorAnalyzer
from .types import ImageItem
import logging

logger = logging.getLogger(__name__)


class SceneDescriptionAnalyzer(SceneAnalyzer):
    """
    Analyzes a scene by combining object detection and color analysis.
    """

    def __init__(self, object_detector: ObjectDetector, color_analyzer: ColorAnalyzer):
        """
        Initialize the scene analyzer with required dependencies.

        Args:
            object_detector: An object detector instance.
            color_analyzer: A color analyzer instance.
        """
        self.object_detector = object_detector
        self.color_analyzer = color_analyzer

    def analyze_scene(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the scene and return a dictionary of scene attributes.

        The returned dictionary includes:
            - 'objects': list of detected objects (from object detector)
            - 'color_analysis': result from color analyzer
            - 'scene_description': a natural language description of the scene

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments passed to the object detector and color analyzer.

        Returns:
            Dictionary containing scene analysis results.
        """
        try:
            # Detect objects
            objects = self.object_detector.detect_objects(image_item, **kwargs)
            # Analyze colors
            color_analysis = self.color_analyzer.analyze_colors(image_item, **kwargs)

            # Generate a simple description
            object_labels = [obj.get('label', 'unknown') for obj in objects]
            # Get the dominant color from the color analysis
            dominant_color = color_analysis.get('dominant_color', [0, 0, 0])
            # Convert to a color name? We'll just use the RGB values for simplicity.
            # In a real system, we might map RGB to color names.
            color_str = f"RGB({dominant_color[0]}, {dominant_color[1]}, {dominant_color[2]})"

            # Count objects by label
            from collections import Counter
            object_counts = Counter(object_labels)
            object_strs = [f"{count} {label}" for label, count in object_counts.items()]
            object_list = ", ".join(object_strs) if object_strs else "no objects detected"

            description = f"A scene containing {object_list}. Dominant color: {color_str}."

            return {
                "objects": objects,
                "color_analysis": color_analysis,
                "scene_description": description
            }
        except Exception as e:
            logger.error(f"Error during scene analysis: {e}")
            raise