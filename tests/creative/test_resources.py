"""
Tests for resource orchestration (C16 phase 16.1, directive V4 §52).

One property carries almost all of these tests: **`None` is not `0`**.

A machine with no GPU has *unknown* VRAM, not zero VRAM. Zero licenses a
conclusion — "24 GiB requested, 0 available, refused" — and that conclusion is
invented, because nobody looked. Unknown forbids concluding, which is the only
honest answer and the one that keeps a provider from being wrongly excluded on
a machine whose GPU simply was not probed.

The second property: nothing unloads by itself. `admit()` names what would have
to be freed and stops there, because only the caller knows whether that model is
still serving a running job.
"""

import pytest

from src.creative.providers import CreativeProvider, LicenceRecord
from src.creative.resources import (
    NON_MESURE,
    ResidencySet,
    ResourceRefused,
    Resources,
    fits,
    measure,
    resources_report,
)
from src.creative.routing import INDETERMINE, NON_SATISFAIT, SATISFAIT


def _fournisseur(identifiant="a", **champs):
    """Un fournisseur déclaré, licence vérifiée."""
    base = {
        "provider_id": identifiant,
        "tasks": frozenset({"text_to_video"}),
        "input_modalities": ("text",),
        "output_modalities": ("video",),
        "licence": LicenceRecord(
            repository="MIT", weights="MIT", commercial="ALLOWED",
            verified_from="https://example.invalid/LICENSE"),
        "runs_locally": True,
    }
    base.update(champs)
    return CreativeProvider(**base)


class TestMesure:
    """Ce qui est lisible est lu ; le reste est nommé absent."""

    def test_le_processeur_et_le_disque_sont_mesures(self):
        mesures = measure(".")
        assert mesures.cpu_count is not None and mesures.cpu_count > 0
        assert mesures.free_disk_gb is not None

    def test_sans_gpu_la_vram_est_inconnue_pas_nulle(self):
        """C'est toute la propriété du module."""
        mesures = measure(".")
        if not mesures.gpu_available:
            assert mesures.vram_gb is None
            assert mesures.vram_gb != 0
            assert mesures.gpu_reason, "Un refus de sonde dit pourquoi."

    def test_une_absence_se_lit_dans_le_rapport(self):
        rendu = measure(".").as_dict()
        if rendu["gpu_available"] is False:
            assert rendu["vram_gb"] == NON_MESURE


class TestTenue:
    """Un besoin confronté à une mesure absente n'est pas satisfait."""

    def test_un_besoin_sans_mesure_reste_indetermine(self):
        verdict = fits(_fournisseur(min_vram_gb=24.0),
                       Resources(vram_gb=None, gpu_reason="aucun GPU"))
        vram = verdict["verdicts"][0]
        assert vram["verdict"] == INDETERMINE
        assert "serait inventé" in vram["reason"]
        # Indéterminé n'écarte pas : personne n'a mesuré.
        assert verdict["loadable"] is True
        assert verdict["unknown"] == ["vram"]

    def test_chargeable_ne_veut_pas_dire_ca_tiendra(self):
        verdict = fits(_fournisseur(min_vram_gb=24.0), Resources(vram_gb=None))
        assert "Ce n'est pas « ça tiendra »" in verdict["note"]

    def test_une_mesure_reelle_tranche(self):
        assert fits(_fournisseur(min_vram_gb=6.0),
                    Resources(vram_gb=8.0))["verdicts"][0]["verdict"] == SATISFAIT
        trop = fits(_fournisseur(min_vram_gb=24.0), Resources(vram_gb=8.0))
        assert trop["verdicts"][0]["verdict"] == NON_SATISFAIT
        assert trop["loadable"] is False

    def test_un_gpu_exige_et_absent_ecarte(self):
        verdict = fits(_fournisseur(requires=("gpu_compute",)),
                       Resources(gpu_available=False, gpu_reason="pas de pilote"))
        gpu = [v for v in verdict["verdicts"] if v["resource"] == "gpu"][0]
        assert gpu["verdict"] == NON_SATISFAIT
        assert verdict["loadable"] is False

    def test_un_fournisseur_sans_besoin_declare_reste_indetermine(self):
        """« Il ne déclare rien » n'est pas « il ne demande rien »."""
        verdict = fits(_fournisseur(), Resources(vram_gb=8.0))
        assert verdict["verdicts"][0]["verdict"] == INDETERMINE


class TestResidence:
    """Rien ne se décharge en silence."""

    def test_un_modele_deja_charge_est_reconnu(self):
        residence = ResidencySet(max_resident=2)
        residence.load("a")
        assert residence.admit(_fournisseur("a"),
                               Resources())["decision"] == "ALREADY_RESIDENT"

    def test_l_admission_suit_les_ressources(self):
        refus = ResidencySet().admit(_fournisseur(min_vram_gb=24.0),
                                     Resources(vram_gb=8.0))
        assert refus["decision"] == "REFUSED"
        assert refus["fit"]["unmet"] == ["vram"]

    def test_la_limite_atteinte_nomme_sans_decharger(self):
        residence = ResidencySet(max_resident=2)
        residence.load("vieux")
        residence.load("recent")
        decision = residence.admit(_fournisseur("nouveau"), Resources())
        assert decision["decision"] == "EVICTION_REQUIRED"
        assert decision["would_evict"] == "vieux"
        # Nommé, pas déchargé : l'appelant seul sait s'il sert encore.
        assert residence.loaded() == ["vieux", "recent"]

    def test_l_usage_recent_change_le_candidat(self):
        residence = ResidencySet(max_resident=2)
        residence.load("a")
        residence.load("b")
        residence.touch("a")
        assert residence.admit(_fournisseur("c"),
                               Resources())["would_evict"] == "b"

    def test_aucune_limite_declaree_n_est_pas_une_absence_de_limite(self):
        decision = ResidencySet().admit(_fournisseur("a"), Resources())
        assert decision["decision"] == "ADMITTED"
        assert decision["residency_limit"] == NON_MESURE
        assert "personne n'a posé" in decision["reason"]

    def test_decharger_ce_qui_n_est_pas_la_est_refuse(self):
        with pytest.raises(ResourceRefused) as erreur:
            ResidencySet().unload("fantome")
        assert "erreur de comptage" in str(erreur.value)

    def test_faire_servir_un_modele_absent_est_refuse(self):
        with pytest.raises(ResourceRefused):
            ResidencySet().touch("fantome")


class TestRapport:
    """Les règles se lisent sans lire le code."""

    def test_la_regle_du_none_est_ecrite(self):
        regles = " ".join(resources_report()["rules"])
        assert "jamais `0`" in regles
        assert "tuer par le noyau" in regles

    def test_la_file_de_travaux_est_renvoyee_a_l_existant(self):
        """Ne pas compter une seconde file (§53)."""
        non_suivi = resources_report()["not_tracked"]
        assert any("existe déjà" in entree["reason"] for entree in non_suivi)
