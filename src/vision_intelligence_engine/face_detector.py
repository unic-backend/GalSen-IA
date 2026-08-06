"""
Détection de visages par cascade de Haar.

Ce détecteur fait une détection réelle quand un fichier de cascade OpenCV est
disponible, et **déclare son indisponibilité** sinon.

Auparavant, il retournait toujours une liste vide : une photo de dix personnes
recevait la réponse « aucun visage détecté ». Un faux négatif présenté comme un
résultat est une invention, au même titre qu'un faux positif — le VOLET 01
chapitre 04 (*Truth and Knowledge Rules*) l'interdit, et le nom de la classe
promettait par-dessus le marché une détection Haar qui n'existait pas.

Les distributions `opencv-python-headless` récentes ne livrent plus les fichiers
de cascade. Le chemin peut donc être fourni explicitement à la construction, ou
via la variable d'environnement `GALSEN_HAARCASCADE_PATH`.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .interfaces import FaceDetector
from .types import ImageItem

logger = logging.getLogger(__name__)


class FaceDetectionUnavailableError(RuntimeError):
    """Levée quand aucune cascade n'est disponible pour détecter des visages."""


class HaarCascadeFaceDetector(FaceDetector):
    """
    Détecteur de visages fondé sur une cascade de Haar (OpenCV).

    Exemple:
        detecteur = HaarCascadeFaceDetector()
        if detecteur.is_available():
            visages = detecteur.detect_faces(image_item)
    """

    CASCADE_ENVIRONMENT_VARIABLE = "GALSEN_HAARCASCADE_PATH"
    DEFAULT_CASCADE_FILENAME = "haarcascade_frontalface_default.xml"

    def __init__(self, cascade_path: Optional[str] = None):
        """
        Initialise le détecteur.

        Args:
            cascade_path: Chemin d'un fichier de cascade. À défaut, la variable
                `GALSEN_HAARCASCADE_PATH`, puis le fichier livré avec OpenCV.
        """
        self._cascade_path = self._resolve_cascade_path(cascade_path)
        self._classifier = None

        if self._cascade_path is None:
            logger.info(
                "Aucune cascade de Haar disponible : la détection de visages est "
                "indisponible. Fournissez %s pour l'activer.",
                self.CASCADE_ENVIRONMENT_VARIABLE,
            )
        else:
            logger.info("Détecteur de visages initialisé avec %s", self._cascade_path)

    @property
    def cascade_path(self) -> Optional[str]:
        """Chemin de la cascade retenue, ou None si aucune n'est disponible."""
        return self._cascade_path

    def is_available(self) -> bool:
        """Indique si une détection réelle est possible, sans charger l'image."""
        return self._cascade_path is not None

    def detect_faces(self, image_item: ImageItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Détecte les visages présents dans l'image.

        Args:
            image_item: Image à analyser.
            **kwargs: `scale_factor` (1.1 par défaut), `min_neighbors` (5),
                `min_size` (30) — paramètres de `detectMultiScale`.

        Returns:
            Une liste de détections `{"bbox": {...}, "confidence": float}`.
            Une liste vide signifie « aucun visage trouvé », ce qui n'est dit
            que lorsqu'une détection a réellement eu lieu.

        Raises:
            FaceDetectionUnavailableError: Si aucune cascade n'est disponible, si
                OpenCV est absent, ou si l'image est illisible. Mieux vaut une
                erreur explicite qu'un « aucun visage » mensonger.
        """
        if not self.is_available():
            raise FaceDetectionUnavailableError(
                "Détection de visages indisponible : aucun fichier de cascade de Haar "
                f"trouvé. Renseignez {self.CASCADE_ENVIRONMENT_VARIABLE} avec le chemin "
                f"d'un fichier '{self.DEFAULT_CASCADE_FILENAME}'."
            )

        try:
            import cv2
            import numpy as np
        except ImportError as error:  # pragma: no cover - dépend de l'installation
            raise FaceDetectionUnavailableError(
                f"Détection de visages indisponible : {error}"
            ) from error

        if self._classifier is None:
            # Les distributions headless récentes d'OpenCV n'embarquent plus le
            # module objdetect : l'absence de la classe est une indisponibilité,
            # pas un plantage à faire remonter tel quel.
            constructeur = getattr(cv2, "CascadeClassifier", None)
            if constructeur is None:
                raise FaceDetectionUnavailableError(
                    "Cette installation d'OpenCV n'expose pas CascadeClassifier "
                    f"(version {getattr(cv2, '__version__', 'inconnue')}). Installez une "
                    "distribution comprenant le module objdetect pour activer la détection."
                )

            self._classifier = constructeur(self._cascade_path)
            if self._classifier.empty():
                raise FaceDetectionUnavailableError(
                    f"Cascade illisible ou vide : {self._cascade_path}"
                )

        image = cv2.imdecode(np.frombuffer(image_item.data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise FaceDetectionUnavailableError(
                "Image illisible : la détection de visages n'a pas pu être tentée."
            )

        gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        taille_minimale = int(kwargs.get("min_size", 30))
        rectangles = self._classifier.detectMultiScale(
            gris,
            scaleFactor=float(kwargs.get("scale_factor", 1.1)),
            minNeighbors=int(kwargs.get("min_neighbors", 5)),
            minSize=(taille_minimale, taille_minimale),
        )

        return [
            {
                "bbox": {"x": int(x), "y": int(y), "width": int(largeur), "height": int(hauteur)},
                # Une cascade de Haar ne produit pas de probabilité : la confiance
                # est fixée à 1.0 pour toute détection retenue, plutôt que d'inventer
                # une valeur intermédiaire qui laisserait croire à une mesure.
                "confidence": 1.0,
            }
            for (x, y, largeur, hauteur) in rectangles
        ]

    def _resolve_cascade_path(self, cascade_path: Optional[str]) -> Optional[str]:
        """
        Détermine le fichier de cascade à utiliser, du plus explicite au défaut.

        Returns:
            Le chemin d'un fichier existant, ou None si aucun n'est disponible.
        """
        candidats = [cascade_path, os.environ.get(self.CASCADE_ENVIRONMENT_VARIABLE)]

        try:
            import cv2

            repertoire = getattr(getattr(cv2, "data", None), "haarcascades", None)
            if repertoire:
                candidats.append(os.path.join(repertoire, self.DEFAULT_CASCADE_FILENAME))
        except ImportError:  # pragma: no cover - dépend de l'installation
            pass

        for candidat in candidats:
            if candidat and os.path.isfile(candidat):
                return candidat
        return None
