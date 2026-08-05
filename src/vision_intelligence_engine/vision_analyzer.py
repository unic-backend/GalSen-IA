"""
Vision analyzer that allows configurable analysis pipelines.
"""

from typing import Dict, Any
from .interfaces import VisionAnalyzer
from .types import ImageItem
from .vision_manager import VisionManagerImpl
import logging

logger = logging.getLogger(__name__)


class VisionAnalyzerImpl(VisionAnalyzer):
    """
    Analyzer that uses a VisionManager to perform selected analyses.
    """

    def __init__(self, vision_manager: Optional[VisionManagerImpl] = None):
        """
        Initialize the analyzer.

        Args:
            vision_manager: An optional VisionManager instance. If not provided, a default one will be created.
        """
        self.vision_manager = vision_manager or VisionManagerImpl()
        logger.info("VisionAnalyzer initialized.")

    def analyze(
        self,
        image_item: ImageItem,
        enable_metadata: bool = True,
        enable_classification: bool = True,
        enable_object_detection: bool = True,
        enable_scene_analysis: bool = True,
        enable_face_detection: bool = True,
        enable_color_analysis: bool = True,
        enable_quality_analysis: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Analyze the image with optional enabling/disabling of specific analyses.

        Args:
            image_item: The image to analyze.
            enable_metadata: Whether to extract metadata.
            enable_classification: Whether to perform image classification.
            enable_object_detection: Whether to detect objects.
            enable_scene_analysis: Whether to analyze the scene.
            enable_face_detection: Whether to detect faces.
            enable_color_analysis: Whether to analyze colors.
            enable_quality_analysis: Whether to analyze quality.
            **kwargs: Additional arguments passed to each analysis method.

        Returns:
            Dictionary containing the results of the enabled analyses.
        """
        results = {}
        try:
            if enable_metadata:
                results["metadata"] = self.vision_manager.extract_metadata(image_item)
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            results["metadata"] = {"error": str(e)}

        try:
            if enable_classification:
                results["classification"] = self.vision_manager.classify_image(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            results["classification"] = {"error": str(e)}

        try:
            if enable_object_detection:
                results["objects"] = self.vision_manager.detect_objects(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Object detection failed: {e}")
            results["objects"] = {"error": str(e)}

        try:
            if enable_scene_analysis:
                results["scene"] = self.vision_manager.analyze_scene(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Scene analysis failed: {e}")
            results["scene"] = {"error": str(e)}

        try:
            if enable_face_detection:
                results["faces"] = self.vision_manager.detect_faces(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Face detection failed: {e}")
            results["faces"] = {"error": str(e)}

        try:
            if enable_color_analysis:
                results["colors"] = self.vision_manager.analyze_colors(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Color analysis failed: {e}")
            results["colors"] = {"error": str(e)}

        try:
            if enable_quality_analysis:
                results["quality"] = self.vision_manager.analyze_quality(image_item, **kwargs)
        except Exception as e:
            logger.warning(f"Quality analysis failed: {e}")
            results["quality"] = {"error": str(e)}

        return results