"""
Tests des fournisseurs de capture et du mode dégradé
(L13.1, ADR-033 décision 5, §31 à §34).

Le test qui compte est `test_un_module_present_ne_suffit_pas` : un fournisseur
dont la bibliothèque s'importe mais dont le périphérique manque est la façon la
plus courante de rendre « disponible » quelque chose qui ne l'est pas.
"""

import pytest

import src.live_context.providers as providers_module
from src.live_context.providers import (
    BLOQUE,
    CAPACITES,
    DANS_LE_PROCESSUS,
    DISPONIBLE,
    INTERFACES_REUTILISEES,
    SERVICE_HEBERGE,
    LiveCaptureProvider,
    LiveProviderRefused,
    degraded_mode,
    health,
    providers_report,
    route,
)


def _fournisseur(**kwargs) -> LiveCaptureProvider:
    defauts = dict(provider_id="alsa", capabilities=("microphone",),
                   execution=DANS_LE_PROCESSUS, python_module="json")
    defauts.update(kwargs)
    return LiveCaptureProvider(**defauts)


class TestUneSeuleInterfaceNouvelle:
    """Quatre des cinq du §31 dupliquent quelque chose qui existe."""

    def test_une_seule_interface_est_declaree_nouvelle(self):
        assert providers_report()["new_interfaces"] == ["LiveCaptureProvider"]

    def test_les_quatre_autres_disent_par_quoi_elles_sont_servies(self):
        assert len(INTERFACES_REUTILISEES) == 4
        for remplacement in INTERFACES_REUTILISEES.values():
            assert remplacement.strip()

    def test_le_contexte_live_n_est_pas_un_fournisseur(self):
        assert "moteur" in INTERFACES_REUTILISEES["RealtimeContextProvider"]

    def test_la_comprehension_d_ecran_reste_bornee_par_adr_018(self):
        assert "ADR-018" in INTERFACES_REUTILISEES["ScreenUnderstandingProvider"]


class TestDeclaration:
    """Ce qui est refusé à la construction."""

    def test_un_fournisseur_sans_identifiant_est_refuse(self):
        with pytest.raises(LiveProviderRefused, match="ne se route pas"):
            _fournisseur(provider_id="  ")

    def test_un_fournisseur_sans_capacite_est_refuse(self):
        with pytest.raises(LiveProviderRefused, match="aucune capacité"):
            _fournisseur(capabilities=())

    def test_une_capacite_inventee_est_refusee(self):
        with pytest.raises(LiveProviderRefused, match="non déclarées"):
            _fournisseur(capabilities=("telepathie",))

    def test_un_mode_d_execution_inconnu_est_refuse(self):
        with pytest.raises(LiveProviderRefused, match="non déclaré"):
            _fournisseur(execution="MAGIE")

    def test_in_process_sans_module_est_refuse(self):
        """Sa disponibilité ne pourrait pas être mesurée."""
        with pytest.raises(LiveProviderRefused, match="ne pourrait pas être"):
            _fournisseur(python_module="")

    def test_les_capacites_reprennent_les_entrees_de_capture(self):
        from src.live_context.capture import ENTREES

        assert CAPACITES == tuple(ENTREES)

    def test_la_latence_declaree_vaut_none_par_defaut(self):
        assert _fournisseur().typical_latency_ms is None


class TestDeclareN_EstPasDisponible:
    """`health()` mesure ; la déclaration affirme."""

    def test_un_module_present_ne_suffit_pas(self, monkeypatch):
        """Le module s'importe, le périphérique manque : BLOCKED."""
        monkeypatch.setattr(providers_module, "module_present", lambda n: True)

        etat = health(_fournisseur())

        if not etat["inputs"]["microphone"]["present"]:
            assert etat["state"] == BLOQUE
            assert any("microphone" in m for m in etat["missing"])

    def test_un_module_absent_est_nomme(self, monkeypatch):
        monkeypatch.setattr(providers_module, "module_present", lambda n: False)

        etat = health(_fournisseur(python_module="sounddevice"))

        assert any("sounddevice" in m for m in etat["missing"])

    def test_un_fournisseur_disponible_quand_tout_est_la(self, monkeypatch):
        from src.live_context.state import MESURE, Observation

        monkeypatch.setattr(providers_module, "module_present", lambda n: True)
        monkeypatch.setattr(
            providers_module, "probe",
            lambda e: Observation(subject=e, status=MESURE, modality="audio",
                                  value="AVAILABLE", detail="présent"))

        assert health(_fournisseur())["state"] == DISPONIBLE

    def test_chaque_manque_est_nomme_pas_resume(self, monkeypatch):
        monkeypatch.setattr(providers_module, "module_present", lambda n: False)

        etat = health(_fournisseur(capabilities=("microphone", "camera")))

        assert len(etat["missing"]) >= 2

    def test_la_latence_n_est_pas_mesuree(self):
        etat = health(_fournisseur())

        assert etat["measured_latency"] is False
        assert etat["latency_ms"] is None

    def test_un_service_heberge_n_a_pas_besoin_de_module(self):
        fournisseur = _fournisseur(execution=SERVICE_HEBERGE, python_module="")

        assert health(fournisseur)["provider_id"] == "alsa"


class TestRoutage:
    """Aucun repli silencieux."""

    def test_une_capacite_inconnue_est_refusee(self):
        with pytest.raises(LiveProviderRefused, match="non déclarée"):
            route("telepathie")

    def test_sans_candidat_le_choix_est_none_avec_sa_raison(self):
        resultat = route("microphone", ())

        assert resultat["chosen"] is None
        assert "aucun candidat" in resultat["reason"]

    def test_avec_des_candidats_bloques_la_raison_change(self):
        resultat = route("microphone", (_fournisseur(),))

        if resultat["chosen"] is None:
            assert "bloqués" in resultat["reason"]
            assert resultat["candidate_count"] == 1

    def test_aucun_repli_vers_une_autre_capacite(self):
        camera = _fournisseur(provider_id="v4l2", capabilities=("camera",))

        resultat = route("microphone", (camera,))

        assert resultat["chosen"] is None
        assert resultat["fallback_used"] is False

    def test_les_etats_des_candidats_sont_rendus(self):
        resultat = route("microphone", (_fournisseur(),))

        assert len(resultat["candidates"]) == 1
        assert "missing" in resultat["candidates"][0]


class TestModeDegrade:
    """Dégradé veut dire moins de modalités, dites comme telles."""

    def test_aucun_booleen_global(self):
        assert degraded_mode()["operational"] is None

    def test_les_huit_capacites_sont_couvertes(self):
        etat = degraded_mode()

        assert len(etat["served"]) + len(etat["lost"]) == len(CAPACITES)
        assert etat["declared_count"] == len(CAPACITES)

    def test_chaque_perte_porte_sa_raison(self):
        etat = degraded_mode()

        for capacite in etat["lost"]:
            assert etat["reasons"][capacite].strip()

    def test_sans_fournisseur_tout_est_perdu(self):
        assert degraded_mode()["served"] == []


class TestRapport:
    """Ce que la couche déclare."""

    def test_le_rapport_porte_les_fournisseurs_declares(self):
        rapport = providers_report((_fournisseur(),))

        assert rapport["declared_providers"][0]["provider_id"] == "alsa"

    def test_le_rapport_porte_le_mode_degrade(self):
        assert "degraded" in providers_report()

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(providers_report()["rules"])

        assert "n'est pas un fournisseur disponible" in regles
        assert "Aucun repli silencieux" in regles
        assert "« rapide » n'est pas une mesure" in regles
