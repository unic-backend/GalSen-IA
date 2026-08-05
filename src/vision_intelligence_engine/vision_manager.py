"""
Vision manager that coordinates all vision components.
"""

from typing import Dict, Any, Optional
from .interfaces import (
    VisionManager,
    ImageLoader,
    ImagePreprocessor,
    ImageMetadataExtractor,
    ImageClassifier,
    ObjectDetector,
    SceneAnalyzer,
    FaceDetector,
    ColorAnalyzer,
    QualityAnalyzer
)
from .types import ImageItem
from .image_loader_factory import ImageLoaderFactory
from .pil_image_loader import PILImageLoader
from .image_preprocessor import SimpleImagePreprocessor
from .image_metadata_extractor import PILImageMetadataExtractor
from .image_classifier import SimpleHistogramClassifier
from .object_detector import ContourObjectDetector
from .face_detector import HaarCascadeFaceDetector
from .color_analyzer import SimpleColorAnalyzer
from .quality_analyzer import SimpleQualityAnalyzer
from .scene_analyzer import SceneDescriptionAnalyzer
import logging

logger = logging.getLogger(__name__)


class VisionManagerImpl(VisionManager):
    """
    Main manager for the vision engine that coordinates all components.
    """

    def __init__(self):
        """Initialize the vision manager and all its components."""
        # Initialize components
        self._init_components()

    def _init_components(self):
        """Initialize all components, logging any failures."""
        # Image Loader
        try:
            self.image_loader = PILImageLoader()
            # Also set up the factory for flexibility
            self.loader_factory = ImageLoaderFactory()
            self.loader_factory.register_loader(".jpg", PILImageLoader)
            self.loader_factory.register_loader(".jpeg", PILImageLoader)
            self.loader_factory.register_loader(".png", PILImageLoader)
            self.loader_factory.register_loader(".webp", PILImageLoader)
            self.loader_factory.register_loader(".bmp", PILImageLoader)
            self.loader_factory.register_loader(".tiff", PILImageLoader)
            self.loader_factory.register_loader(".tif", PILImageLoader)
            logger.info("Image loader initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize image loader: {e}")
            self.image_loader = None
            self.loader_factory = None

        # Image Preprocessor
        try:
            self.image_preprocessor = SimpleImagePreprocessor()
            logger.info("Image preprocessor initialized.")
        except Exception as e:
            self.image_preprocessor = None
            logger.warning(f"Failed to initialize image preprocessor: {e}")

        # Image Metadata Extractor
        try:
            self.image_metadata_extractor = PILImageMetadataExtractor()
            logger.info("Image metadata extractor initialized.")
        except Exception as e:
            self.image_metadata_extractor = None
            logger.warning(f"Failed to initialize image metadata extractor: {e}")

        # Image Classifier
        try:
            self.image_classifier = SimpleHistogramClassifier()
            logger.info("Image classifier initialized.")
        except Exception as e:
            self.image_classifier = None
            logger.warning(f"Failed to initialize image classifier: {e}")

        # Object Detector
        try:
            self.object_detector = ContourObjectDetector()
            logger.info("Object detector initialized.")
        except Exception as e:
            self.object_detector = None
            logger.warning(f"Failed to initialize object detector: {e}")

        # Face Detector
        try:
            self.face_detector = HaarCascadeFaceDetector()
            logger.info("Face detector initialized.")
        except Exception as e:
            self.face_detector = None
            logger.warning(f"Failed to initialize face detector: {e}")

        # Color Analyzer
        try:
            self.color_analyzer = SimpleColorAnalyzer()
            logger.info("Color analyzer initialized.")
        except Exception as e:
            self.color_analyzer = None
            logger.warning(f"Failed to initialize color analyzer: {e}")

        # Quality Analyzer
        try:
            self.quality_analyzer = SimpleQualityAnalyzer()
            logger.info("Quality analyzer initialized.")
        except Exception as e:
            self.quality_analyzer = None
            logger.warning(f"Failed to initialize quality analyzer: {e}")

        # Scene Analyzer (requires object detector and color analyzer)
        try:
            if self.object_detector is not None and self.color_analyzer is not None:
                self.scene_analyzer = SceneDescriptionAnalyzer(
                    object_detector=self.object_detector,
                    color_analyzer=self.color_analyzer
                )
                logger.info("Scene analyzer initialized.")
            else:
                self.scene_analyzer = None
                missing = []
                if self.object_detector is None:
                    missing.append("object detector")
                if self.color_analyzer is None:
                    missing.append("color analyzer")
                logger.warning(f"Failed to initialize scene analyzer due to missing dependencies: {', '.join(missing)}")
        except Exception as e:
            self.scene_analyzer = None
            logger.warning(f"Failed to initialize scene analyzer: {e}")

    def analyze_image(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Perform a full analysis of the image using all available components.
        Returns a dictionary containing results from all analyses.
        """
        results = {}
        # If no image loader, we cannot load images, but we can still process an existing ImageItem
        # For analysis, we need the image_item to have data.

        # Metadata
        if self.image_metadata_extractor:
            try:
                results["metadata"] = self.image_metadata_extractor.extract_metadata(image_item)
            except Exception as e:
                results["metadata"] = {"error": str(e)}
        else:
            results["metadata"] = {"error": "Component not available"}

        # Classification
        if self.image_classifier:
            try:
                results["classification"] = self.image_classifier.classify(image_item, **kwargs)
            except Exception as e:
                results["classification"] = {"error": str(e)}
        else:
            results["classification"] = {"error": "Component not available"}

        # Object Detection
        if self.object_detector:
            try:
                results["objects"] = self.object_detector.detect_objects(image_item, **kwargs)
            except Exception as e:
                results["objects"] = {"error": str(e)}
        else:
            results["objects"] = {"error": "Component not available"}

        # Face Detection
        if self.face_detector:
            try:
                results["faces"] = self.face_detector.detect_faces(image_item, **kwargs)
            except Exception as e:
                results["faces"] = {"error": str(e)}
        else:
            results["faces"] = {"error": "Component not available"}

        # Color Analysis
        if self.color_analyzer:
            try:
                results["colors"] = self.color_analyzer.analyze_colors(image_item, **kwargs)
            except Exception as e:
                results["colors"] = {"error": str(e)}
        else:
            results["colors"] = {"error": "Component not available"}

        # Quality Analysis
        if self.quality_analyzer:
            try:
                results["quality"] = self.quality_analyzer.analyze_quality(image_item, **kwargs)
            except Exception as e:
                results["quality"] = {"error": str(e)}
        else:
            results["quality"] = {"error": "Component not available"}

        # Scene Analysis
        if self.scene_analyzer:
            try:
                results["scene"] = self.scene_analyzer.analyze_scene(image_item, **kwargs)
            except Exception as e:
                results["scene"] = {"error": str(e)}
        else:
            results["scene"] = {"error": "Component not available"}

        return results

    def load_image(self, source: str, **kwargs) -> ImageItem:
        """
        Load an image from a source.

        Args:
            source: Path or URL to the image.
            **kwargs: Additional arguments for the loader.

        Returns:
            ImageItem representing the loaded image.
        """
        if self.image_loader is None:
            raise RuntimeError("Image loader is not available.")
        return self.image_loader.load(source, **kwargs)

    def preprocess_image(self, image_item: ImageItem, **kwargs) -> ImageItem:
        """
        Preprocess an image.

        Args:
            image_item: The image to preprocess.
            **kwargs: Additional arguments for the preprocessor.

        Returns:
            Preprocessed ImageItem.
        """
        if self.image_preprocessor is None:
            raise RuntimeError("Image preprocessor is not available.")
        return self.image_preprocessor.preprocess(image_item, **kwargs)

    def extract_metadata(self, image_item: ImageItem) -> Dict[str, Any]:
        """
        Extract metadata from an image.

        Args:
            image_item: The image to analyze.

        Returns:
            Dictionary of metadata.
        """
        if self.image_metadata_extractor is None:
            return {"error": "Component not available"}
        return self.image_metadata_extractor.extract_metadata(image_item)

    def classify_image(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Classify an image.

        Args:
            image_item: The image to classify.
            **kwargs: Additional arguments for the classifier.

        Returns:
            Classification result.
        """
        if self.image_classifier is None:
            return {"error": "Component not available"}
        return self.image_classifier.classify(image_item, **kwargs)

    def detect_objects(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Detect objects in an image.

        Args:
            image_item: The image to process.
            **kwargs: Additional arguments for the detector.

        Returns:
            List of detections.
        """
        if self.object_detector is None:
            return {"error": "Component not available"}
        return self.object_detector.detect_objects(image_item, **kwargs)

    def detect_faces(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Detect faces in an image.

        Args:
            image_item: The image to process.
            **kwargs: Additional arguments for the detector.

        Returns:
            List of face detections.
        """
        if self.face_detector is None:
            return {"error": "Component not available"}
        return self.face_detector.detect_faces(image_item, **kwargs)

    def analyze_colors(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Analyze colors in an image.

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments for the analyzer.

        Returns:
            Color analysis result.
        """
        if self.color_analyzer is None:
            return {"error": "Component not available"}
        return self.color_analyzer.analyze_colors(image_item, **kwargs)

    def analyze_quality(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Analyze quality of an image.

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments for the analyzer.

        Returns:
            Quality analysis result.
        """
        if self.quality_analyzer is None:
            return {"error": "Component not available"}
        return self.quality_analyzer.analyze_quality(image_item, **kwargs)

    def analyze_scene(self, image_item: ImageItem, **kwargs) -> Any:
        """
        Analyze the scene in an image.

        Args:
            image_item: The image to analyze.
            **kwargs: Additional arguments for the analyzer.

        Returns:
            Scene analysis result.
        """
        if self.scene_analyzer is None:
            return {"error": "Component not available"}
        return self.scene_analyzer.analyze_scene(image_item, **kwargs)