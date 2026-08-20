"""
Tests de la surface de capture (L05.2, ADR-033, §7).

**Aucun test n'épingle les spécificités de cette machine.** Un test affirmant
« pas de microphone » passerait ici et échouerait sur le portable d'un
développeur qui en a un — ce serait un test non déterministe, et un test non
déterministe finit par être ignoré.

Ce qui est vérifié est donc le **comportement** : que la sonde interroge
l'environnement, que toute absence porte son constat, et qu'aucun booléen global
ne remplace le détail. Les cas présents et absents sont produits en remplaçant
les sondes.
"""

import pytest

import src.live_context.capture as capture
from src.live_context.capture import (
    DISPONIBLE,
    ENTREES,
    CaptureRefused,
    available_modalities,
    capture_report,
    capture_surface,
    probe,
)
from src.live_context.state import ABSENT, MESURE


class TestEntreesDeclarees:
    """Les huit entrées du §7."""

    def test_les_huit_entrees_sont_declarees(self):
        assert len(ENTREES) == 8
        assert "microphone" in ENTREES and "screen" in ENTREES

    def test_une_entree_inconnue_est_refusee(self):
        with pytest.raises(CaptureRefused, match="non déclarée"):
            probe("telepathie")

    def test_chaque_entree_se_sonde(self):
        for entree in ENTREES:
            assert probe(entree).subject == entree


class TestToutConstatEstDonne:
    """« Absent » sans constat est une supposition."""

    def test_chaque_entree_porte_un_detail(self):
        for entree in ENTREES:
            assert probe(entree).detail.strip(), entree

    def test_chaque_absence_nomme_ce_qui_a_ete_cherche(self):
        for observation in (probe(e) for e in ENTREES):
            if observation.status == ABSENT:
                assert observation.detail.strip()

    def test_une_entree_presente_est_mesuree_et_vaut_disponible(self, monkeypatch):
        monkeypatch.setattr(capture, "_sonde_microphone",
                            lambda: (True, "/dev/snd présent"))

        observation = capture.probe("microphone")

        assert observation.status == MESURE
        assert observation.value == DISPONIBLE

    def test_une_entree_absente_ne_porte_aucune_valeur(self, monkeypatch):
        monkeypatch.setattr(capture, "_sonde_microphone",
                            lambda: (False, "/dev/snd cherché, absent"))

        observation = capture.probe("microphone")

        assert observation.status == ABSENT
        assert observation.value is None
        assert "cherché" in observation.detail


class TestSurface:
    """La surface rend le détail, jamais un verdict global."""

    def test_les_comptes_couvrent_les_huit_entrees(self):
        surface = capture_surface()

        assert surface["available_count"] + surface["absent_count"] == 8

    def test_aucun_score_n_est_rendu(self):
        assert capture_surface()["score"] is None

    def test_aucun_booleen_global_ne_remplace_le_detail(self):
        surface = capture_surface()

        assert not any(isinstance(v, bool) for v in surface.values())

    def test_chaque_absence_est_rendue_avec_sa_raison(self):
        for manquante in capture_surface()["absent"]:
            assert manquante["input"] in ENTREES
            assert manquante["reason"].strip()

    def test_la_surface_est_stable_d_un_appel_a_l_autre(self):
        premier = capture_surface()["available"]
        second = capture_surface()["available"]

        assert premier == second


class TestModalitesDynamiques:
    """§7 : déterminer dynamiquement quelles modalités sont disponibles."""

    def test_les_modalites_viennent_des_entrees_disponibles(self, monkeypatch):
        monkeypatch.setattr(capture, "_sonde_microphone", lambda: (False, "absent"))
        monkeypatch.setattr(capture, "_sonde_camera", lambda: (False, "absent"))
        monkeypatch.setattr(capture, "_sonde_ecran", lambda: (False, "absent"))
        monkeypatch.setattr(capture, "_sonde_media", lambda: (False, "absent"))
        monkeypatch.setattr(capture, "_module_present", lambda nom: False)

        assert available_modalities() == ["text"]

    def test_un_ecran_disponible_ajoute_sa_modalite(self, monkeypatch):
        monkeypatch.setattr(capture, "_sonde_ecran", lambda: (True, "DISPLAY=:0"))

        assert "screen" in available_modalities()

    def test_une_modalite_disponible_ne_veut_pas_dire_capture_live(self, monkeypatch):
        """`audio` peut venir d'un fichier téléversé, pas d'un microphone."""
        monkeypatch.setattr(capture, "_sonde_microphone", lambda: (False, "absent"))
        monkeypatch.setattr(capture, "_module_present", lambda nom: True)

        assert "audio" in available_modalities()
        assert capture.probe("microphone").status == ABSENT


class TestRapport:
    """Le rapport dit ce qui est tenu, et ce que le module ne fait pas."""

    def test_le_module_ne_capture_rien(self):
        assert capture_report()["captures_anything"] is False

    def test_le_rapport_declare_les_huit_entrees(self):
        assert capture_report()["declared_inputs"] == list(ENTREES)

    def test_la_regle_de_mesure_est_ecrite(self):
        regles = " ".join(capture_report()["rules"])

        assert "interrogeant l'environnement" in regles
        assert "ADR-018" in regles

    def test_le_rapport_porte_la_surface_et_les_modalites(self):
        rapport = capture_report()

        assert "surface" in rapport
        assert isinstance(rapport["modalities_available"], list)
