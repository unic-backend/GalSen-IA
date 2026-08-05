"""
Tests unitaires de l'outil modèle.

L'outil expose le moteur de modèles à travers le moteur d'outils. Le point
important est qu'une génération impossible retourne un statut au lieu de lever :
un agent doit pouvoir constater qu'aucun fournisseur n'a répondu et retomber sur
un travail déterministe.

Le moteur est simulé : aucun appel de modèle n'est fait.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.model.tool import ModelTool


@pytest.fixture
def moteur():
    """Moteur de modèles simulé, sans fournisseur disponible par défaut."""
    faux = MagicMock()
    faux.has_available_provider.return_value = False
    faux.unavailability_reason.return_value = "Aucun fournisseur configuré"
    faux.select_model_for_task.return_value = None
    return faux


@pytest.fixture
def outil(moteur):
    """Outil branché sur le moteur simulé."""
    instance = ModelTool()
    instance._engine = moteur
    return instance


class TestGenerationIndisponible:
    """Vérifie qu'une génération impossible est signalée, jamais levée."""

    def test_generate_sans_modele_retourne_un_statut(self, outil):
        """Sans modèle sélectionnable, le statut doit valoir `unavailable`."""
        resultat = outil.execute("generate", "Bonjour")
        assert resultat["status"] == "unavailable"
        assert resultat["text"] == ""
        assert "Aucun fournisseur configuré" in resultat["detail"]

    def test_generate_sans_modele_ne_leve_pas(self, outil):
        """L'absence de fournisseur ne doit pas interrompre l'agent appelant."""
        outil.execute("generate", "Bonjour")  # ne doit pas lever

    def test_available_reflete_le_moteur(self, outil, moteur):
        """`available` doit refléter l'état réel du moteur."""
        assert outil.execute("available") is False
        moteur.has_available_provider.return_value = True
        assert outil.execute("available") is True

    def test_status_agrege_les_fournisseurs(self, outil, moteur):
        """`status` doit remonter l'état des fournisseurs et la raison."""
        moteur.get_provider_status.return_value = {"ollama": "unavailable"}
        etat = outil.execute("status")
        assert etat["providers"] == {"ollama": "unavailable"}
        assert etat["any_available"] is False
        assert etat["detail"] == "Aucun fournisseur configuré"


class TestGenerationDisponible:
    """Vérifie le passage des paramètres au moteur quand un modèle répond."""

    @pytest.fixture
    def moteur_pret(self, moteur):
        """Moteur simulé avec un modèle sélectionnable et une réponse."""
        modele = MagicMock()
        moteur.select_model_for_task.return_value = modele
        reponse = MagicMock()
        reponse.to_dict.return_value = {"status": "ready", "text": "Bonjour Dakar"}
        moteur.generate.return_value = reponse
        return moteur

    def test_generate_retourne_le_texte(self, outil, moteur_pret):
        """La réponse du moteur doit être retournée telle quelle."""
        resultat = outil.execute("generate", "Salue Dakar")
        assert resultat == {"status": "ready", "text": "Bonjour Dakar"}

    def test_parametres_par_defaut_transmis(self, outil, moteur_pret):
        """Les valeurs par défaut de l'outil doivent atteindre le moteur."""
        outil.execute("generate", "Salue Dakar")
        _, options = moteur_pret.generate.call_args
        assert options["max_tokens"] == 1024
        assert options["temperature"] == 0.7

    def test_parametres_de_l_appel_priment(self, outil, moteur_pret):
        """Les options passées à l'appel doivent primer sur les défauts."""
        outil.execute("generate", "Salue Dakar", max_tokens=64, temperature=0.1,
                      system_prompt="Réponds en wolof")
        _, options = moteur_pret.generate.call_args
        assert options["max_tokens"] == 64
        assert options["temperature"] == 0.1
        assert options["system_prompt"] == "Réponds en wolof"

    def test_configuration_de_l_outil_remplace_les_defauts(self, moteur_pret):
        """La configuration de l'outil doit fixer les valeurs par défaut."""
        instance = ModelTool({"max_tokens": 256, "temperature": 0.2})
        instance._engine = moteur_pret
        instance.execute("generate", "Salue Dakar")
        _, options = moteur_pret.generate.call_args
        assert options["max_tokens"] == 256
        assert options["temperature"] == 0.2

    def test_exigences_de_tache_transmises_a_la_selection(self, outil, moteur_pret):
        """Les exigences doivent guider la sélection, sans polluer la génération."""
        outil.execute("generate", "Résume", task_type="summarization", complexity="high")
        moteur_pret.select_model_for_task.assert_called_once_with(
            {"task_type": "summarization", "complexity": "high"}
        )

    def test_modele_impose_court_circuite_la_selection(self, outil, moteur_pret):
        """Un `model_name` explicite doit contourner la sélection automatique."""
        outil.execute("generate", "Salue", model_name="llama3")
        moteur_pret._model_registry.to_model_item.assert_called_once_with("llama3")
        moteur_pret.select_model_for_task.assert_not_called()


class TestCatalogueEtSelection:
    """Vérifie les opérations de consultation du catalogue."""

    def test_catalogue_complet_par_defaut(self, outil, moteur):
        """Par défaut, tout le catalogue doit être retourné."""
        moteur.list_catalogue.return_value = [{"name": "llama3"}]
        assert outil.execute("catalogue") == [{"name": "llama3"}]
        moteur.list_catalogue.assert_called_once_with(available_only=False)

    def test_catalogue_filtre(self, outil, moteur):
        """`available_only` doit être transmis au moteur."""
        moteur.list_catalogue.return_value = []
        outil.execute("catalogue", available_only=True)
        moteur.list_catalogue.assert_called_once_with(available_only=True)

    def test_select(self, outil, moteur):
        """`select` doit transmettre les exigences au moteur."""
        moteur.select_provider_for_task.return_value = {"provider": "ollama"}
        assert outil.execute("select", task_type="chat") == {"provider": "ollama"}
        moteur.select_provider_for_task.assert_called_once_with({"task_type": "chat"})

    def test_explain(self, outil, moteur):
        """`explain` doit retourner le raisonnement de sélection."""
        moteur.explain_selection.return_value = {"reason": "seul fournisseur local"}
        assert outil.execute("explain", task_type="chat")["reason"] == "seul fournisseur local"

    def test_capabilities_modele_absent(self, outil, moteur):
        """Un modèle absent du catalogue doit être refusé explicitement."""
        moteur._model_registry.to_model_item.return_value = None
        with pytest.raises(ValueError, match="absent du catalogue"):
            outil.execute("capabilities", "modele-inconnu")

    def test_capabilities_modele_present(self, outil, moteur):
        """Les capacités d'un modèle connu doivent être retournées."""
        moteur._cd.discover_capabilities.return_value = {"vision": False}
        assert outil.execute("capabilities", "llama3") == {"vision": False}


class TestContratOutil:
    """Vérifie le contrat commun et le partage du moteur."""

    def test_invite_vide_refusee(self, outil):
        """Une invite vide doit être refusée avant d'atteindre le moteur."""
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            outil.execute("generate", "   ")

    def test_operation_inconnue(self, outil):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            outil.execute("entrainer_un_modele")

    def test_operation_manquante(self, outil):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            outil.execute()

    def test_available_operations(self, outil):
        """La liste annoncée doit couvrir les opérations réelles."""
        assert {"generate", "status", "catalogue", "select"} <= set(outil.available_operations())

    def test_moteur_partage_de_la_plateforme(self):
        """L'outil doit passer par le registre commun, pas par son propre moteur."""
        instance = ModelTool()
        with patch("src.integration.engine_registry.get_shared_registry") as registre:
            registre.return_value.model = MagicMock(name="moteur-partagé")
            instance._op_available()
        registre.assert_called_once()
