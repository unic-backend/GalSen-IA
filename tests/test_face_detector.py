"""
Tests du détecteur de visages.

L'enjeu est de distinguer deux réponses que l'ancienne version confondait :
« aucun visage sur cette image » et « je ne sais pas détecter de visages ». La
première n'est dite que lorsqu'une détection a réellement eu lieu ; la seconde
est une erreur explicite.

Aucun modèle n'est téléchargé : les tests fabriquent une cascade minimale ou
simulent OpenCV.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.vision_intelligence_engine.face_detector import (
    FaceDetectionUnavailableError,
    HaarCascadeFaceDetector,
)
from src.vision_intelligence_engine.types import ImageItem


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Retire toute cascade héritée de l'environnement réel."""
    monkeypatch.delenv(HaarCascadeFaceDetector.CASCADE_ENVIRONMENT_VARIABLE, raising=False)


@pytest.fixture
def image():
    """Image de test, dont le contenu importe peu : OpenCV est simulé."""
    return ImageItem(image_id="test", data=b"donnees-image")


@pytest.fixture
def cascade(tmp_path):
    """Fichier de cascade factice : seule son existence compte pour la résolution."""
    fichier = tmp_path / "haarcascade_frontalface_default.xml"
    fichier.write_text("<opencv_storage></opencv_storage>", encoding="utf-8")
    return str(fichier)


class TestIndisponibilite:
    """Vérifie qu'une détection impossible est dite, jamais déguisée en zéro visage."""

    def test_non_disponible_sans_cascade(self):
        """Sans fichier de cascade, le détecteur se déclare indisponible."""
        with patch.object(HaarCascadeFaceDetector, "_resolve_cascade_path", return_value=None):
            assert HaarCascadeFaceDetector().is_available() is False

    def test_erreur_explicite_plutot_qu_une_liste_vide(self, image):
        """Sans cascade, la détection doit lever et non retourner « aucun visage »."""
        with patch.object(HaarCascadeFaceDetector, "_resolve_cascade_path", return_value=None):
            detecteur = HaarCascadeFaceDetector()
            with pytest.raises(FaceDetectionUnavailableError, match="aucun fichier de cascade"):
                detecteur.detect_faces(image)

    def test_le_message_dit_comment_activer(self, image):
        """L'erreur doit indiquer la variable à renseigner."""
        with patch.object(HaarCascadeFaceDetector, "_resolve_cascade_path", return_value=None):
            with pytest.raises(FaceDetectionUnavailableError, match="GALSEN_HAARCASCADE_PATH"):
                HaarCascadeFaceDetector().detect_faces(image)

    def test_cascade_illisible(self, image, cascade):
        """Une cascade vide ou corrompue doit être signalée comme telle."""
        detecteur = HaarCascadeFaceDetector(cascade_path=cascade)
        classifieur = MagicMock()
        classifieur.empty.return_value = True
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True):
            with pytest.raises(FaceDetectionUnavailableError, match="illisible ou vide"):
                detecteur.detect_faces(image)

    def test_image_illisible(self, image, cascade):
        """Une image que le décodeur refuse ne doit pas devenir « aucun visage »."""
        detecteur = HaarCascadeFaceDetector(cascade_path=cascade)
        classifieur = MagicMock()
        classifieur.empty.return_value = False
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True), \
             patch("cv2.imdecode", return_value=None, create=True):
            with pytest.raises(FaceDetectionUnavailableError, match="Image illisible"):
                detecteur.detect_faces(image)


class TestResolutionDeLaCascade:
    """Vérifie l'ordre de recherche du fichier de cascade."""

    def test_chemin_explicite(self, cascade):
        """Un chemin fourni à la construction doit primer."""
        assert HaarCascadeFaceDetector(cascade_path=cascade).cascade_path == cascade

    def test_variable_d_environnement(self, cascade, monkeypatch):
        """La variable d'environnement doit être utilisée à défaut."""
        monkeypatch.setenv(HaarCascadeFaceDetector.CASCADE_ENVIRONMENT_VARIABLE, cascade)
        assert HaarCascadeFaceDetector().cascade_path == cascade

    def test_chemin_inexistant_ignore(self, tmp_path, monkeypatch):
        """Un chemin qui ne pointe sur aucun fichier ne doit pas être retenu."""
        monkeypatch.setenv(
            HaarCascadeFaceDetector.CASCADE_ENVIRONMENT_VARIABLE, str(tmp_path / "absent.xml")
        )
        with patch("cv2.data", None):
            assert HaarCascadeFaceDetector().cascade_path is None

    def test_priorite_du_chemin_explicite_sur_l_environnement(self, cascade, tmp_path, monkeypatch):
        """Le chemin explicite doit primer sur la variable d'environnement."""
        autre = tmp_path / "autre.xml"
        autre.write_text("<opencv_storage></opencv_storage>", encoding="utf-8")
        monkeypatch.setenv(HaarCascadeFaceDetector.CASCADE_ENVIRONMENT_VARIABLE, str(autre))
        assert HaarCascadeFaceDetector(cascade_path=cascade).cascade_path == cascade


class TestDetectionReelle:
    """Vérifie la détection quand une cascade est disponible."""

    def _detecteur_avec_rectangles(self, cascade, rectangles):
        """Prépare un détecteur dont le classifieur retourne les rectangles fournis."""
        classifieur = MagicMock()
        classifieur.empty.return_value = False
        classifieur.detectMultiScale.return_value = rectangles
        return HaarCascadeFaceDetector(cascade_path=cascade), classifieur

    def test_aucun_visage_trouve(self, image, cascade):
        """Une détection réelle sans résultat retourne bien une liste vide."""
        detecteur, classifieur = self._detecteur_avec_rectangles(cascade, [])
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True), \
             patch("cv2.imdecode", return_value=MagicMock(), create=True), \
             patch("cv2.cvtColor", return_value=MagicMock(), create=True):
            assert detecteur.detect_faces(image) == []

    def test_visages_trouves(self, image, cascade):
        """Chaque rectangle doit devenir une détection exploitable."""
        detecteur, classifieur = self._detecteur_avec_rectangles(
            cascade, [(10, 20, 30, 40), (50, 60, 70, 80)]
        )
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True), \
             patch("cv2.imdecode", return_value=MagicMock(), create=True), \
             patch("cv2.cvtColor", return_value=MagicMock(), create=True):
            visages = detecteur.detect_faces(image)

        assert len(visages) == 2
        assert visages[0]["bbox"] == {"x": 10, "y": 20, "width": 30, "height": 40}
        assert visages[0]["confidence"] == 1.0
        assert all(0.0 <= v["confidence"] <= 1.0 for v in visages)

    def test_parametres_transmis(self, image, cascade):
        """Les paramètres de détection doivent atteindre OpenCV."""
        detecteur, classifieur = self._detecteur_avec_rectangles(cascade, [])
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True), \
             patch("cv2.imdecode", return_value=MagicMock(), create=True), \
             patch("cv2.cvtColor", return_value=MagicMock(), create=True):
            detecteur.detect_faces(image, scale_factor=1.3, min_neighbors=8, min_size=64)

        _, options = classifieur.detectMultiScale.call_args
        assert options["scaleFactor"] == 1.3
        assert options["minNeighbors"] == 8
        assert options["minSize"] == (64, 64)

    def test_classifieur_construit_une_seule_fois(self, image, cascade):
        """La cascade ne doit être chargée qu'une fois, pas à chaque image."""
        detecteur, classifieur = self._detecteur_avec_rectangles(cascade, [])
        with patch("cv2.CascadeClassifier", return_value=classifieur, create=True) as constructeur, \
             patch("cv2.imdecode", return_value=MagicMock(), create=True), \
             patch("cv2.cvtColor", return_value=MagicMock(), create=True):
            detecteur.detect_faces(image)
            detecteur.detect_faces(image)
        constructeur.assert_called_once()
