"""
Tests de l'outil calendrier.

L'enjeu principal de ces tests est négatif : l'outil ne doit **rien inventer**.
Avant leur réécriture, ils affirmaient l'inverse — ils vérifiaient que
`get_events` retourne bien « Réunion d'équipe » et « Déjeuner avec client »,
deux rendez-vous fabriqués, et que `add_event` répond `success` sans rien créer.
Des tests verts protégeaient donc une invention.

Aucun calendrier n'est raccordé à ce jour : chaque opération doit annoncer son
indisponibilité, tandis que la validation des entrées, elle bien réelle, reste
appliquée.
"""

import pytest

from src.tools.calendar.tool import CalendarTool


@pytest.fixture
def calendar_tool():
    """Return a CalendarTool instance with default configuration."""
    return CalendarTool()


class TestAucuneInvention:
    """Vérifie que l'outil ne fabrique aucune donnée d'agenda."""

    def test_get_events_n_invente_aucun_evenement(self, calendar_tool):
        """La lecture d'agenda ne doit retourner aucun événement fabriqué."""
        result = calendar_tool.execute("get_events")
        assert result["status"] == "unavailable"
        assert result["events"] == []

    def test_get_events_explique_pourquoi(self, calendar_tool):
        """L'appelant doit savoir pourquoi il n'obtient rien."""
        result = calendar_tool.execute("get_events")
        assert "Aucun calendrier" in result["detail"]
        assert "connecteur" in result["detail"]

    def test_les_anciens_rendez_vous_fictifs_ont_disparu(self, calendar_tool):
        """Les deux rendez-vous fabriqués ne doivent plus exister nulle part."""
        rendu = str(calendar_tool.execute("get_events"))
        assert "Réunion d'équipe" not in rendu
        assert "Déjeuner avec client" not in rendu

    def test_add_event_ne_pretend_pas_avoir_cree(self, calendar_tool):
        """Une création impossible ne doit jamais être annoncée comme réussie."""
        result = calendar_tool.execute(
            "add_event",
            title="Réunion Dakar",
            start="2026-08-01T10:00:00",
            end="2026-08-01T11:00:00",
        )
        assert result["status"] == "unavailable"
        assert result["status"] != "success"
        assert result["event_id"] is None

    def test_delete_event_ne_pretend_pas_avoir_supprime(self, calendar_tool):
        """Une suppression impossible ne doit jamais être annoncée comme réussie."""
        result = calendar_tool.execute("delete_event", event_id="event123")
        assert result["status"] == "unavailable"
        assert result["deleted"] is False


class TestValidationDesEntrees:
    """Vérifie la validation, qui est réelle et doit précéder l'indisponibilité."""

    @pytest.mark.parametrize("titre", ["", "   ", None, 42])
    def test_titre_invalide(self, calendar_tool, titre):
        """Un titre vide ou d'un type inattendu doit être refusé."""
        with pytest.raises(ValueError, match="titre de l'événement doit être une chaîne non vide"):
            calendar_tool.execute(
                "add_event", title=titre,
                start="2026-08-01T10:00:00", end="2026-08-01T11:00:00",
            )

    def test_date_de_debut_invalide(self, calendar_tool):
        """Une date de début vide doit être refusée."""
        with pytest.raises(ValueError, match="date de début doit être une chaîne non vide"):
            calendar_tool.execute(
                "add_event", title="Réunion", start="", end="2026-08-01T11:00:00",
            )

    def test_date_de_fin_invalide(self, calendar_tool):
        """Une date de fin vide doit être refusée."""
        with pytest.raises(ValueError, match="date de fin doit être une chaîne non vide"):
            calendar_tool.execute(
                "add_event", title="Réunion", start="2026-08-01T10:00:00", end="",
            )

    @pytest.mark.parametrize("identifiant", ["", None])
    def test_identifiant_invalide(self, calendar_tool, identifiant):
        """Un identifiant d'événement vide doit être refusé."""
        with pytest.raises(ValueError, match="identifiant de l'événement doit être une chaîne non vide"):
            calendar_tool.execute("delete_event", event_id=identifiant)

    def test_la_validation_precede_l_indisponibilite(self, calendar_tool):
        """Une demande mal formée est refusée même si aucun calendrier n'existe.

        L'appelant doit d'abord corriger ce qui dépend de lui : recevoir
        « indisponible » sur une requête invalide masquerait son erreur.
        """
        with pytest.raises(ValueError):
            calendar_tool.execute("add_event", title="", start="", end="")


class TestContratOutil:
    """Vérifie le contrat commun à tous les outils."""

    def test_initialisation(self, calendar_tool):
        """L'outil doit s'instancier sans configuration."""
        assert calendar_tool is not None

    def test_available_operations(self, calendar_tool):
        """La liste annoncée doit correspondre aux opérations réelles."""
        assert set(calendar_tool.available_operations()) == {
            "get_events", "add_event", "delete_event",
        }

    def test_operation_inconnue(self, calendar_tool):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            calendar_tool.execute("synchroniser_tout")

    def test_operation_manquante(self, calendar_tool):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            calendar_tool.execute()
