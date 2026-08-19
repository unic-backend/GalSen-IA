"""
Tests de la déclaration d'un fournisseur de recherche (R04.1, STEP 4).

Les tests qui comptent sont `TestAucunSecret` — une déclaration ne porte jamais
de valeur d'authentification — et `TestSanteMesuree`, qui vérifie que l'état est
mesuré contre l'environnement et non écrit.
"""

import pytest

from src.creative.canvas.privacy import ProviderPrivacyPolicy
from src.creative.providers import LicenceRecord
from src.research.providers import (
    BLOQUE,
    CAPACITES,
    DANS_LE_PROCESSUS,
    DISPONIBLE,
    MODES_D_EXECUTION,
    SOUS_PROCESSUS,
    ResearchProvider,
    ResearchProviderRefused,
    declared_providers,
    health,
    provider,
    providers_report,
    providers_serving,
)
from src.security.trust import TrustLevel


def _fournisseur(**kwargs) -> ResearchProvider:
    defauts = dict(provider_id="essai", capabilities=("web_search",),
                   execution=DANS_LE_PROCESSUS, python_module="json")
    defauts.update(kwargs)
    return ResearchProvider(**defauts)


class TestDeclaration:
    """Ce qui est refusé à la construction."""

    def test_un_fournisseur_sans_identifiant_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="ne se route pas"):
            _fournisseur(provider_id="  ")

    def test_un_fournisseur_sans_capacite_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="aucune capacité"):
            _fournisseur(capabilities=())

    def test_une_capacite_inventee_est_refusee(self):
        with pytest.raises(ResearchProviderRefused, match="non déclarées"):
            _fournisseur(capabilities=("web_search", "telepathie"))

    def test_un_mode_d_execution_inconnu_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="non déclaré"):
            _fournisseur(execution="MAGIE")

    def test_in_process_sans_module_est_refuse(self):
        """Sans module, la disponibilité ne pourrait pas être mesurée."""
        with pytest.raises(ResearchProviderRefused, match="sans module"):
            _fournisseur(python_module="")

    def test_subprocess_sans_executable_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="sans exécutable"):
            _fournisseur(execution=SOUS_PROCESSUS, python_module="",
                         executable="")

    def test_une_latence_negative_est_refusee(self):
        with pytest.raises(ResearchProviderRefused, match="impossible"):
            _fournisseur(typical_latency_ms=-5)


class TestAucunSecret:
    """Une déclaration porte des noms de variables, jamais leurs valeurs."""

    def test_une_valeur_deguisee_en_nom_est_refusee(self):
        with pytest.raises(ResearchProviderRefused, match="pas à un nom"):
            _fournisseur(authentication=("EXA_API_KEY=sk-abc123",))

    def test_un_nom_trop_long_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="pas à un nom"):
            _fournisseur(authentication=("A" * 80,))

    def test_la_serialisation_ne_contient_aucune_valeur(self, monkeypatch):
        monkeypatch.setenv("ESSAI_TOKEN", "secret-a-ne-pas-fuiter")
        serialise = _fournisseur(authentication=("ESSAI_TOKEN",)).as_dict()

        assert serialise["authentication"] == ["ESSAI_TOKEN"]
        assert "secret-a-ne-pas-fuiter" not in str(serialise)

    def test_la_sante_ne_contient_aucune_valeur(self, monkeypatch):
        monkeypatch.setenv("ESSAI_TOKEN", "secret-a-ne-pas-fuiter")
        etat = health(_fournisseur(authentication=("ESSAI_TOKEN",)))

        assert "secret-a-ne-pas-fuiter" not in str(etat)


class TestSanteMesuree:
    """L'état est mesuré contre l'environnement, jamais écrit."""

    def test_un_module_present_rend_disponible(self):
        assert health(_fournisseur(python_module="json"))["state"] == DISPONIBLE

    def test_un_module_absent_bloque_en_le_nommant(self):
        etat = health(_fournisseur(python_module="module_qui_n_existe_pas_xyz"))

        assert etat["state"] == BLOQUE
        assert "module_qui_n_existe_pas_xyz" in str(etat["missing"])

    def test_un_programme_absent_bloque(self):
        etat = health(_fournisseur(execution=SOUS_PROCESSUS, python_module="",
                                   executable="programme-absent-xyz"))

        assert etat["state"] == BLOQUE

    def test_une_variable_absente_bloque(self, monkeypatch):
        monkeypatch.delenv("VARIABLE_ABSENTE_XYZ", raising=False)
        etat = health(_fournisseur(authentication=("VARIABLE_ABSENTE_XYZ",)))

        assert etat["state"] == BLOQUE

    def test_une_variable_posee_ne_bloque_plus(self, monkeypatch):
        monkeypatch.setenv("VARIABLE_POSEE_XYZ", "x")

        assert health(_fournisseur(
            authentication=("VARIABLE_POSEE_XYZ",)))["state"] == DISPONIBLE

    def test_chaque_manque_nomme_le_geste_qui_le_repare(self):
        etat = health(_fournisseur(python_module="module_absent_xyz",
                                   authentication=("VAR_ABSENTE_XYZ",)))

        assert len(etat["missing"]) == 2
        assert all(m["repair"].strip() for m in etat["missing"])

    def test_une_exigence_externe_bloque_toujours(self):
        """Ce qui dépend d'un opérateur ne se mesure pas ici."""
        etat = health(_fournisseur(requires=("une session Chrome de bureau",)))

        assert etat["state"] == BLOQUE


class TestConfiance:
    """Le contenu récupéré est une donnée (STEP 6)."""

    def test_sans_politique_la_confiance_est_externe(self):
        assert _fournisseur().trust_level == TrustLevel.EXTERNAL

    def test_une_destination_locale_rend_tool(self):
        politique = ProviderPrivacyPolicy(provider_id="essai",
                                          data_destination="LOCAL_ONLY")

        assert _fournisseur(privacy=politique).trust_level == TrustLevel.TOOL

    def test_les_trois_fournisseurs_declares_sont_externes(self):
        """Aucune politique n'a été établie : UNKNOWN retombe sur EXTERNAL."""
        for fournisseur in declared_providers():
            assert fournisseur.trust_level == TrustLevel.EXTERNAL


class TestSelection:
    """Chercher un fournisseur, sans jamais les classer."""

    def test_une_capacite_inventee_est_refusee(self):
        """Une liste vide se lirait comme « personne ne sait le faire »."""
        with pytest.raises(ResearchProviderRefused, match="non déclarée"):
            providers_serving("telepathie")

    def test_la_recherche_academique_n_a_qu_un_fournisseur(self):
        servants = providers_serving("academic_search")

        assert [p.provider_id for p in servants] == ["web_search_mcp"]

    def test_la_recherche_web_en_a_trois(self):
        assert len(providers_serving("web_search")) == 3

    def test_un_fournisseur_inconnu_est_refuse(self):
        with pytest.raises(ResearchProviderRefused, match="non déclaré"):
            provider("inexistant")

    def test_le_fournisseur_interne_est_declare_au_meme_format(self):
        interne = provider("existing_galsen_research")

        assert interne.execution == DANS_LE_PROCESSUS
        assert interne.serves("web_search")


class TestFournisseursDeclares:
    """Ce que les audits ont lu est encodé, pas résumé."""

    def test_agent_reach_est_un_sous_processus(self):
        """Sa seule classe publique porte deux méthodes de diagnostic (R01)."""
        assert provider("agent_reach").execution == SOUS_PROCESSUS

    def test_web_search_mcp_est_importable(self):
        assert provider("web_search_mcp").execution == DANS_LE_PROCESSUS

    def test_aucun_candidat_n_est_degage_commercialement(self):
        for identifiant in ("web_search_mcp", "agent_reach"):
            assert provider(identifiant).licence.usable_commercially is False

    def test_les_licences_nomment_leur_source(self):
        for identifiant in ("web_search_mcp", "agent_reach"):
            assert provider(identifiant).licence.verified_from.startswith("http")

    def test_agent_reach_porte_la_trouvaille_des_cli_sans_licence(self):
        restrictions = provider("agent_reach").licence.restrictions

        assert "licence" in restrictions.lower()

    def test_chaque_candidat_declare_ses_limites(self):
        for identifiant in ("web_search_mcp", "agent_reach"):
            assert provider(identifiant).limitations


class TestRapport:
    """Le rapport dit ce qui est tenu."""

    def test_le_rapport_compte_les_etats_mesures(self):
        rapport = providers_report()

        assert rapport["available_count"] + rapport["blocked_count"] == 3

    def test_les_deux_candidats_sont_bloques_ici(self):
        etats = {e["provider_id"]: e["state"] for e in providers_report()["health"]}

        assert etats["web_search_mcp"] == BLOQUE
        assert etats["agent_reach"] == BLOQUE

    def test_le_rapport_nomme_les_types_reutilises(self):
        """Aucun de ces trois types n'est réécrit ici."""
        reutilises = providers_report()["reused_types"]

        assert "creative.providers.LicenceRecord" in reutilises
        assert "creative.canvas.privacy.ProviderPrivacyPolicy" in reutilises

    def test_le_vocabulaire_est_celui_declare(self):
        rapport = providers_report()

        assert rapport["capabilities"] == list(CAPACITES)
        assert rapport["execution_modes"] == list(MODES_D_EXECUTION)

    def test_le_champ_ne_s_appelle_pas_invocation(self):
        """ADR-031 : ce mot porte déjà deux sens opposés dans ce dépôt."""
        serialise = provider("agent_reach").as_dict()

        assert "execution" in serialise
        assert "invocation" not in serialise

    def test_les_types_reutilises_le_sont_vraiment(self):
        interne = provider("existing_galsen_research")

        assert isinstance(interne.licence, LicenceRecord)
        assert isinstance(interne.privacy, ProviderPrivacyPolicy)
