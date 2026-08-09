"""
Tests du versionnage (VOLET_04 ch. 03).

Une version qui dépend de l'endroit où on la lit ne permet plus de dire ce qui
tourne. C'est exactement ce qui était arrivé : `0.1.0` dans l'application,
`0.2.0` dans l'étiquette de l'image Docker, aucune des deux ne correspondant à
quoi que ce soit de publié.

`src/version.py` est désormais la source unique. Le Dockerfile ne pouvant pas
importer du Python, il redéclare la valeur en argument de construction — et ces
tests échouent si les deux s'écartent.
"""

import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.server import app  # noqa: E402
from src.version import __release_type__, __version__  # noqa: E402

RACINE = os.path.join(os.path.dirname(__file__), "..")

# Types de version admis par le VOLET_04 chapitre 03.
TYPES_ADMIS = ("prototype", "alpha", "beta", "stable", "lts")


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as instance:
        yield instance


def _dockerfile() -> str:
    """Retourne le contenu du Dockerfile livré."""
    with open(os.path.join(RACINE, "Dockerfile"), encoding="utf-8") as fichier:
        return fichier.read()


class TestFormat:
    """Le numéro doit respecter le versionnage sémantique."""

    def test_versionnage_semantique(self):
        """`MAJEUR.MINEUR.CORRECTIF`, sans quoi la comparaison n'a plus de sens."""
        assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", __version__), __version__

    def test_type_de_version_reconnu(self):
        """Un type inventé ne dirait rien à qui lit le chapitre 03."""
        assert __release_type__ in TYPES_ADMIS

    def test_serie_zero_tant_que_le_type_n_est_pas_stable(self):
        """En 0.x, tout peut changer — c'est ce que promet un prototype.

        Annoncer 1.0.0 engage la compatibilité ascendante. Tant que le type de
        version n'est pas `stable`, la série majeure doit rester à 0.
        """
        majeur = int(__version__.split(".")[0])
        if __release_type__ in ("prototype", "alpha", "beta"):
            assert majeur == 0, (
                f"Version {__version__} annoncée comme « {__release_type__} » : "
                "une majeure ≥ 1 promet une stabilité que ce type ne tient pas."
            )


class TestSourceUnique:
    """Un seul endroit décide, les autres s'y conforment."""

    def test_l_api_annonce_la_meme_version(self, client):
        """`/health` sert à savoir ce qui tourne : il doit dire la vérité."""
        assert app.version == __version__
        assert client.get("/health").json()["version"] == __version__

    def test_l_image_docker_annonce_la_meme_version(self):
        """C'est la divergence qui a motivé ce fichier : 0.1.0 contre 0.2.0."""
        trouve = re.search(r"^ARG GALSEN_VERSION=(\S+)", _dockerfile(), re.MULTILINE)
        assert trouve, "Le Dockerfile doit déclarer ARG GALSEN_VERSION."
        assert trouve.group(1) == __version__, (
            f"Dockerfile : {trouve.group(1)} — src/version.py : {__version__}"
        )

    def test_l_etiquette_utilise_l_argument(self):
        """Une étiquette écrite en dur redeviendrait une seconde source."""
        assert 'org.opencontainers.image.version="${GALSEN_VERSION}"' in _dockerfile()

    def test_aucune_version_en_dur_dans_le_serveur(self):
        """`version=\"0.1.0\"` dans `FastAPI(...)` est ce qui avait divergé."""
        with open(os.path.join(RACINE, "src", "api", "server.py"), encoding="utf-8") as f:
            source = f.read()
        assert re.search(r'version\s*=\s*"\d+\.\d+\.\d+"', source) is None


class TestCoherenceAvecLEtatDuProjet:
    """Le type de version est une promesse : elle doit être tenable."""

    def test_pas_de_promesse_de_stabilite_sans_deploiement(self, client):
        """`stable` ou `lts` supposent au minimum une plateforme utilisable.

        Aujourd'hui aucun fournisseur de modèles n'est configuré : la
        fonctionnalité principale répond 503. Annoncer une version stable dans
        cet état serait une promesse que rien ne tient.
        """
        if __release_type__ in ("stable", "lts"):
            sante = client.get("/health").json()
            assert sante["status"] == "healthy", (
                "Version annoncée stable alors que /health ne rapporte pas healthy."
            )
