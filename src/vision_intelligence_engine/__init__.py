"""
Moteur de vision : analyse une image et rapporte ce qu'il en observe.

Responsabilités
    Charger une image, la préparer, en extraire des métadonnées, analyser ses
    couleurs, sa qualité et sa scène, détecter objets et visages. Chaque
    analyse rapporte son état : une capacité indisponible ne renvoie jamais un
    résultat plausible.

Interfaces publiques
    `VisionManagerImpl` est le point d'entrée ; `VisionAnalyzer` compose les
    analyses. `interfaces.py` définit les contrats, `types.py` les résultats.

Dépendances
    Pillow et OpenCV (`opencv-python-headless`). OpenCV est importé au niveau
    module par plusieurs composants : sans lui, le moteur `vision` est déclaré
    indisponible par `EngineRegistry` au lieu de tomber en cours d'appel.

Configuration
    `GALSEN_HAARCASCADE_PATH` pour le modèle de détection de visages.

Limites connues
    Le moteur est le moins couvert de la plateforme (53-63 % sur ses composants
    principaux, 0 % sur `contour_object_detector.py`), parce que ses tests
    dépendent d'OpenCV et d'images réelles. La classification d'images repose
    sur un modèle générique, pas sur un modèle entraîné pour les cas d'usage du
    projet.
"""

from .vision_manager import VisionManagerImpl
from .vision_analyzer import VisionAnalyzerImpl
from .interfaces import (
    ImageLoader,
    ImagePreprocessor,
    ImageMetadataExtractor,
    ImageClassifier,
    ObjectDetector,
    SceneAnalyzer,
    FaceDetector,
    ColorAnalyzer,
    QualityAnalyzer,
    VisionManager,
    VisionAnalyzer
)
from .types import ImageItem, ImageType, ImageStatus

__all__ = [
    "VisionManagerImpl",
    "VisionAnalyzerImpl",
    "ImageLoader",
    "ImagePreprocessor",
    "ImageMetadataExtractor",
    "ImageClassifier",
    "ObjectDetector",
    "SceneAnalyzer",
    "FaceDetector",
    "ColorAnalyzer",
    "QualityAnalyzer",
    "VisionManager",
    "VisionAnalyzer",
    "ImageItem",
    "ImageType",
    "ImageStatus"
]