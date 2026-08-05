"""
Interfaces for the Vision Intelligence Engine components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from .types import ImageItem, ImageType


class ImageLoader(ABC):
    """Interface for loading images from various sources."""

    @abstractmethod
    def load(self, source: str, **kwargs) -> ImageItem:
        """Load an image from a source (file path, URL, etc.) and return an ImageItem."""
        pass

    @abstractmethod
    def supports_type(self, image_type: ImageType) -> bool:
        """Check if this loader supports the given image type."""
        pass


class ImagePreprocessor(ABC):
    """Interface for preprocessing images (e.g., resizing, normalization)."""

    @abstractmethod
    def preprocess(self, image_item: ImageItem, **kwargs) -> ImageItem:
        """Preprocess the image and return a new ImageItem with processed data."""
        pass


class ImageMetadataExtractor(ABC):
    """Interface for extracting metadata from images."""

    @abstractmethod
    def extract_metadata(self, image_item: ImageItem) -> Dict[str, Any]:
        """Extract metadata from the image and return a dictionary of metadata."""
        pass


class ImageClassifier(ABC):
    """Interface for classifying images into categories."""

    @abstractmethod
    def classify(self, image_item: ImageItem, **kwargs) -> List[Tuple[str, float]]:
        """
        Classify the image and return a list of (class_label, confidence_score) tuples.
        """
        pass


class ObjectDetector(ABC):
    """Interface for detecting objects in images."""

    @abstractmethod
    def detect_objects(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Detect objects in the image and return a list of detections.
        Each detection is a dictionary with keys like 'label', 'confidence', 'bbox' (bounding box).
        """
        pass


class SceneAnalyzer(ABC):
    """Interface for analyzing scenes in images (e.g., indoor/outdoor, landscape type)."""

    @abstractmethod
    def __init__(self, object_detector: ObjectDetector, color_analyzer: ColorAnalyzer):
        """Initialize the scene analyzer with required dependencies."""
        pass

    @abstractmethod
    def analyze_scene(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the scene and return a dictionary of scene attributes.
        """
        pass


class FaceDetector(ABC):
    """Interface for detecting faces in images (without identity recognition)."""

    @abstractmethod
    def detect_faces(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Detect faces in the image and return a list of face detections.
        Each detection is a dictionary with keys like 'confidence', 'bbox' (bounding box).
        """
        pass


class ColorAnalyzer(ABC):
    """Interface for analyzing colors in images."""

    @abstractmethod
    def analyze_colors(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the colors in the image and return a dictionary of color statistics.
        """
        pass


class QualityAnalyzer(ABC):
    """Interface for analyzing image quality (e.g., blur, exposure, noise)."""

    @abstractmethod
    def analyze_quality(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Analyze the quality of the image and return a dictionary of quality metrics.
        """
        pass


class VisionManager(ABC):
    """Main interface for the vision engine that coordinates all components."""

    @abstractmethod
    def analyze_image(self, image_item: ImageItem, **kwargs) -> Dict[str, Any]:
        """
        Perform a full analysis of the image using all available components.
        Returns a dictionary containing results from all analyses.
        """
        pass

    @abstractmethod
    def load_image(self, source: str, **kwargs) -> ImageItem:
        """Load an image from a source."""
        pass


class VisionAnalyzer(ABC):
    """Interface for analyzing images with configurable components."""

    @abstractmethod
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
        """
        pass