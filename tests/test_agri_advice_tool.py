"""
Tests unitaires de l'outil de conseil agricole.

C'est le premier outil destiné aux utilisateurs sénégalais : il doit produire un
conseil quand un modèle répond, et dire clairement qu'aucun n'a répondu sinon —
jamais planter. Les tests couvrent aussi la construction de l'invite, qui porte
le contexte sénégalais et la langue de réponse.

Le gestionnaire de modèles est simulé : aucun appel de modèle n'est fait.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.agri_advice.tool import AgriAdviceTool


@pytest.fixture
def gestionnaire():
    """Gestionnaire de modèles simulé, sans modèle disponible par défaut."""
    faux = MagicMock()
    faux.select_model_for_task.return_value = None
    faux.unavailability_reason.return_value = "Aucun fournisseur configuré"
    return faux


@pytest.fixture
def connaissance_fiable():
    """Gestionnaire de connaissances simulé, avec une connaissance fiable.

    La garde de fiabilité appelle `retrieve_reliable` sur le moteur partagé ;
    sans cet injecteur, les tests de génération tomberaient sur la base réelle
    (vide) et la garde refuserait de générer.
    """
    faux = MagicMock()
    faux.retrieve_reliable.return_value = {"items": [], "reliable": True}
    return faux


@pytest.fixture
def outil(gestionnaire, connaissance_fiable):
    """Outil branché sur les gestionnaires simulés."""
    instance = AgriAdviceTool()
    instance._model_manager = gestionnaire
    instance._knowledge_manager = connaissance_fiable
    return instance


@pytest.fixture
def gestionnaire_pret(gestionnaire):
    """Gestionnaire simulé avec un modèle qui répond."""
    modele = MagicMock()
    modele.name = "llama3"
    gestionnaire.select_model_for_task.return_value = modele
    reponse = MagicMock()
    reponse.to_dict.return_value = {
        "status": "ready",
        "text": "  Le mil se sème dès les premières pluies, en juin.  ",
    }
    gestionnaire.generate.return_value = reponse
    return gestionnaire


class TestAucunModeleDisponible:
    """Vérifie que l'absence de modèle est une information, pas une panne."""

    def test_statut_unavailable(self, outil):
        """Sans modèle, le statut doit valoir `unavailable`."""
        resultat = outil.execute("get_advice", "Quand planter le mil ?")
        assert resultat["status"] == "unavailable"
        assert resultat["answer"] == ""
        assert resultat["model_used"] is None

    def test_raison_transmise(self, outil):
        """La raison de l'indisponibilité doit être remontée à l'appelant."""
        resultat = outil.execute("get_advice", "Quand planter le mil ?")
        assert "Aucun fournisseur configuré" in resultat["detail"]

    def test_ne_leve_pas(self, outil):
        """L'absence de modèle ne doit pas interrompre l'agent appelant."""
        outil.execute("get_advice", "Quand planter le mil ?")  # ne doit pas lever

    def test_langue_conservee_meme_sans_modele(self, outil):
        """La langue demandée doit être rapportée dans tous les cas."""
        assert outil.execute("get_advice", "Kañ lañuy ji dugub ?", language="wo")["language"] == "wo"


class TestConseilGenere:
    """Vérifie le conseil produit quand un modèle répond."""

    def test_reponse_nettoyee(self, outil, gestionnaire_pret):
        """La réponse doit être retournée sans espaces superflus."""
        resultat = outil.execute("get_advice", "Quand planter le mil à Thiès ?")
        assert resultat["status"] == "ready"
        assert resultat["answer"] == "Le mil se sème dès les premières pluies, en juin."
        assert resultat["model_used"] == "llama3"

    def test_invite_porte_le_contexte_senegalais(self, outil, gestionnaire_pret):
        """L'invite envoyée au modèle doit situer le conseil au Sénégal."""
        outil.execute("get_advice", "Quand planter le mil ?")
        invite = gestionnaire_pret.generate.call_args[0][1]
        assert "sénégalais" in invite
        assert "Quand planter le mil ?" in invite

    def test_invite_en_francais_par_defaut(self, outil, gestionnaire_pret):
        """Sans langue précisée, l'invite doit demander une réponse en français."""
        outil.execute("get_advice", "Quand planter le mil ?")
        assert "Réponds en français" in gestionnaire_pret.generate.call_args[0][1]

    def test_invite_en_wolof(self, outil, gestionnaire_pret):
        """La langue wolof doit changer l'instruction envoyée au modèle."""
        outil.execute("get_advice", "Kañ lañuy ji dugub ?", language="wo")
        assert "Wolof" in gestionnaire_pret.generate.call_args[0][1]

    def test_langue_par_defaut_configurable(self, gestionnaire_pret, connaissance_fiable):
        """La configuration doit pouvoir fixer la langue par défaut."""
        instance = AgriAdviceTool({"language": "wo"})
        instance._model_manager = gestionnaire_pret
        instance._knowledge_manager = connaissance_fiable
        assert instance.execute("get_advice", "Kañ lañuy ji dugub ?")["language"] == "wo"

    def test_exigences_de_tache_transmises(self, outil, gestionnaire_pret):
        """La sélection doit être guidée par le domaine et la région."""
        outil.execute("get_advice", "Quand planter le mil ?")
        gestionnaire_pret.select_model_for_task.assert_called_once_with(
            {"domain": "agriculture", "region": "Senegal", "language": "fr"}
        )

    def test_parametres_de_generation_transmis(self, outil, gestionnaire_pret):
        """max_tokens et temperature doivent atteindre le moteur quand ils sont fournis."""
        outil.execute("get_advice", "Quand planter le mil ?", max_tokens=128, temperature=0.3)
        _, options = gestionnaire_pret.generate.call_args
        assert options == {"max_tokens": 128, "temperature": 0.3}

    def test_aucun_parametre_impose_par_defaut(self, outil, gestionnaire_pret):
        """Sans option, l'outil ne doit pas imposer de paramètres au moteur."""
        outil.execute("get_advice", "Quand planter le mil ?")
        assert gestionnaire_pret.generate.call_args[1] == {}

    def test_modele_impose(self, outil, gestionnaire_pret):
        """Un `model_id` explicite doit contourner la sélection automatique."""
        modele = MagicMock()
        modele.name = "modele-impose"
        gestionnaire_pret.get_model.return_value = modele
        resultat = outil.execute("get_advice", "Quand planter le mil ?", model_id="modele-impose")
        assert resultat["model_used"] == "modele-impose"
        gestionnaire_pret.select_model_for_task.assert_not_called()


class TestContratOutil:
    """Vérifie le contrat commun et le partage du gestionnaire."""

    @pytest.mark.parametrize("invalide", ["", "   ", None, 42])
    def test_question_invalide_refusee(self, outil, invalide):
        """Une question vide ou d'un type inattendu doit être refusée."""
        with pytest.raises(ValueError, match="chaîne non vide"):
            outil.execute("get_advice", invalide)

    def test_operation_inconnue(self, outil):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            outil.execute("predire_la_recolte")

    def test_operation_manquante(self, outil):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            outil.execute()

    def test_available_operations(self, outil):
        """La liste annoncée doit correspondre aux opérations réelles."""
        assert outil.available_operations() == ["get_advice"]

    def test_gestionnaire_partage_de_la_plateforme(self):
        """L'outil doit passer par le registre commun, pas par son propre moteur."""
        instance = AgriAdviceTool()
        with patch("src.integration.engine_registry.get_shared_registry") as registre:
            registre.return_value.model = MagicMock(name="moteur-partagé")
            assert instance.model_manager is registre.return_value.model
        registre.assert_called_once()
