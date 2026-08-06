"""
Tests du routeur de modèles.

Le routeur apporte ce que `generate()` ne fait pas : compter les échecs, écarter
un modèle qui tombe, basculer sur le candidat suivant. Avant sa réécriture il
retournait `"Réponse simulée du modèle X"` — un texte fabriqué qu'aucun appelant
n'aurait pu distinguer d'une vraie réponse.

Le point le plus important testé ici : un fournisseur **ne lève pas** quand il
échoue, il retourne un statut. Le routeur doit interpréter la réponse, sinon un
`unavailable` compterait comme un succès et la bascule ne partirait jamais.
"""

from unittest.mock import MagicMock

import pytest

from src.model_engine.model_router import FailoverModelRouter, ModelRoutingError
from src.model_engine.providers.base import (
    GenerationResponse,
    ProviderStatus,
    UnavailabilityReason,
)


def _modele(identifiant: str) -> MagicMock:
    """Construit un modèle simulé portant un identifiant."""
    modele = MagicMock()
    modele.model_id = identifiant
    modele.name = identifiant
    modele.provider = "test"
    return modele


def _reponse_reussie(texte: str = "Bonjour Dakar") -> GenerationResponse:
    """Réponse exploitable d'un fournisseur."""
    return GenerationResponse(status=ProviderStatus.READY, text=texte, model_name="test")


def _reponse_indisponible(detail: str = "pas de clé") -> GenerationResponse:
    """Réponse d'un fournisseur qui n'a pas pu servir la requête."""
    return GenerationResponse.unavailable(
        provider_id="test", model_name="test",
        reason=UnavailabilityReason.NO_CREDENTIALS, detail=detail,
    )


@pytest.fixture
def requete():
    """Requête minimale acceptée par le routeur."""
    return {"prompt": "Bonjour"}


class TestGenerationReelle:
    """Vérifie que le routeur appelle bien la génération qu'on lui donne."""

    def test_la_reponse_vient_du_generateur_injecte(self, requete):
        """Aucun texte ne doit être fabriqué par le routeur lui-même."""
        generer = MagicMock(return_value=_reponse_reussie("Réponse réelle"))
        routeur = FailoverModelRouter(generer)
        reponse = routeur.route_request(_modele("m1"), requete)
        assert reponse.text == "Réponse réelle"
        assert "simulée" not in reponse.text

    def test_options_transmises(self, requete):
        """Les options de génération doivent atteindre le générateur."""
        generer = MagicMock(return_value=_reponse_reussie())
        routeur = FailoverModelRouter(generer)
        routeur.route_request(
            _modele("m1"),
            {**requete, "max_tokens": 64, "temperature": 0.2, "system_prompt": "Sois bref"},
        )
        _, options = generer.call_args
        assert options == {"max_tokens": 64, "temperature": 0.2, "system_prompt": "Sois bref"}

    def test_cles_inconnues_ignorees(self, requete):
        """Une clé étrangère à la génération ne doit pas être transmise."""
        generer = MagicMock(return_value=_reponse_reussie())
        FailoverModelRouter(generer).route_request(
            _modele("m1"), {**requete, "cle_inconnue": "valeur"},
        )
        assert "cle_inconnue" not in generer.call_args[1]

    def test_invite_vide_refusee(self):
        """Une requête sans invite doit être refusée avant tout appel."""
        generer = MagicMock()
        with pytest.raises(ValueError, match="invite non vide"):
            FailoverModelRouter(generer).route_request(_modele("m1"), {"prompt": "  "})
        generer.assert_not_called()


class TestInterpretationDuStatut:
    """Vérifie que le routeur lit le statut, sans se fier à l'absence d'exception."""

    def test_reponse_indisponible_compte_comme_un_echec(self, requete):
        """Un statut non `READY` doit lever, sinon la bascule ne partirait jamais."""
        generer = MagicMock(return_value=_reponse_indisponible("clé absente"))
        routeur = FailoverModelRouter(generer)
        with pytest.raises(ModelRoutingError, match="clé absente"):
            routeur.route_request(_modele("m1"), requete)

    def test_texte_vide_compte_comme_un_echec(self, requete):
        """Un statut `READY` sans texte n'est pas un succès exploitable."""
        vide = GenerationResponse(status=ProviderStatus.READY, text="", model_name="test")
        routeur = FailoverModelRouter(MagicMock(return_value=vide))
        with pytest.raises(ModelRoutingError):
            routeur.route_request(_modele("m1"), requete)

    def test_exception_du_generateur_propagee(self, requete):
        """Une panne du générateur reste une panne, et est comptée."""
        routeur = FailoverModelRouter(MagicMock(side_effect=RuntimeError("réseau coupé")))
        with pytest.raises(RuntimeError, match="réseau coupé"):
            routeur.route_request(_modele("m1"), requete)
        assert routeur._failure_counts["m1"] == 1


class TestComptageDesEchecs:
    """Vérifie la mémoire des échecs, qui décide de la santé d'un modèle."""

    def test_echec_incremente_le_compteur(self, requete):
        """Chaque échec doit être retenu."""
        routeur = FailoverModelRouter(MagicMock(return_value=_reponse_indisponible()))
        for _ in range(2):
            with pytest.raises(ModelRoutingError):
                routeur.route_request(_modele("m1"), requete)
        assert routeur._failure_counts["m1"] == 2

    def test_succes_remet_le_compteur_a_zero(self, requete):
        """Un modèle qui répond de nouveau redevient sain."""
        generer = MagicMock(side_effect=[_reponse_indisponible(), _reponse_reussie()])
        routeur = FailoverModelRouter(generer)
        with pytest.raises(ModelRoutingError):
            routeur.route_request(_modele("m1"), requete)
        routeur.route_request(_modele("m1"), requete)
        assert "m1" not in routeur._failure_counts

    def test_modele_ecarte_apres_le_seuil(self, requete):
        """Au-delà du seuil, le modèle est considéré comme non sain."""
        routeur = FailoverModelRouter(MagicMock(return_value=_reponse_indisponible()))
        for _ in range(3):
            with pytest.raises(ModelRoutingError):
                routeur.route_request(_modele("m1"), requete)
        assert routeur._is_model_healthy("m1") is False


class TestBascule:
    """Vérifie le passage d'un modèle au suivant."""

    def test_bascule_sur_le_candidat_suivant(self, requete):
        """Le premier modèle qui répond doit fournir la réponse."""
        generer = MagicMock(side_effect=[_reponse_indisponible(), _reponse_reussie("depuis m2")])
        routeur = FailoverModelRouter(generer)
        reponse = routeur.route_with_fallback([_modele("m1"), _modele("m2")], requete)
        assert reponse.text == "depuis m2"
        assert generer.call_count == 2

    def test_premier_modele_prioritaire(self, requete):
        """Si le premier répond, les suivants ne doivent pas être appelés."""
        generer = MagicMock(return_value=_reponse_reussie("depuis m1"))
        routeur = FailoverModelRouter(generer)
        reponse = routeur.route_with_fallback([_modele("m1"), _modele("m2")], requete)
        assert reponse.text == "depuis m1"
        assert generer.call_count == 1

    def test_tous_en_echec(self, requete):
        """Quand aucun candidat ne répond, l'erreur doit le dire."""
        routeur = FailoverModelRouter(MagicMock(return_value=_reponse_indisponible("rien")))
        with pytest.raises(ModelRoutingError, match="Tous les modèles ont échoué"):
            routeur.route_with_fallback([_modele("m1"), _modele("m2")], requete)


class TestRepartitionDeCharge:
    """Vérifie la répartition entre modèles sains."""

    def test_un_modele_sain_est_choisi(self, requete):
        """La répartition doit aboutir à une génération réelle."""
        generer = MagicMock(return_value=_reponse_reussie())
        routeur = FailoverModelRouter(generer)
        reponse = routeur.route_with_load_balancing([_modele("m1"), _modele("m2")], requete)
        assert reponse.succeeded is True
        assert generer.call_count == 1

    def test_compteurs_reinitialises_si_aucun_modele_sain(self, requete):
        """Aucun modèle sain ne doit pas bloquer la plateforme."""
        routeur = FailoverModelRouter(MagicMock(return_value=_reponse_reussie()))
        routeur._failure_counts = {"m1": 5, "m2": 5}
        routeur.route_with_load_balancing([_modele("m1"), _modele("m2")], requete)
        assert routeur._failure_counts.get("m1", 0) == 0
