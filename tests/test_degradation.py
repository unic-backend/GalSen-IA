"""
Un sous-système absent n'en fait tomber aucun autre (phase 65.1).

`EngineRegistry` isole depuis longtemps les quatorze moteurs des premiers
VOLETs : celui qui ne se construit pas est rapporté indisponible et ne propage
jamais son exception. Cette garantie n'a jamais été étendue à ce qui a été
construit après. À la fin du VOLET 64, dix sous-systèmes de plus existent —
routines, points de reprise, canaux, connaissance mondiale, routage, greffons,
couches de mémoire, bac à sable, registre de sources, orchestration — et aucun
n'apparaissait dans le moindre rapport de disponibilité.

Ce que ces tests gardent :

1. **La sonde qui tombe est rapportée, jamais propagée.** Un rapport de
   dégradation renversé par ce qu'il observe serait la panne qu'il doit
   empêcher.
2. **Dégradé n'est pas en panne.** Un sous-système qui dit ce qui lui manque
   fonctionne comme prévu.
3. **Chaque état dit ce qui fonctionne encore sans lui** — sinon un exploitant
   ne sait pas s'il doit agir ce soir ou lundi.
4. **Un fichier de déclaration absent se distingue d'une déclaration vide.**
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integration.degradation import (  # noqa: E402
    DEGRADE,
    DISPONIBLE,
    INDISPONIBLE,
    SOUS_SYSTEMES,
    degradation_report,
    probe,
)


# ----------------------------------------------------------------------
# 1. La sonde qui tombe ne renverse rien
# ----------------------------------------------------------------------

def test_une_sonde_qui_leve_est_rapportee_indisponible(monkeypatch):
    """C'est le cas que tout ce module existe pour tenir."""
    def _casse():
        raise RuntimeError("le disque a disparu")

    monkeypatch.setitem(SOUS_SYSTEMES["plugins"], "probe", _casse)

    etat = probe("plugins")

    assert etat["state"] == INDISPONIBLE
    assert "le disque a disparu" in etat["reason"]


def test_une_sonde_cassee_ne_fait_pas_tomber_le_rapport(monkeypatch):
    """Les autres sous-systèmes sont mesurés quand même."""
    def _casse():
        raise RuntimeError("panne")

    monkeypatch.setitem(SOUS_SYSTEMES["plugins"], "probe", _casse)

    rapport = degradation_report(["plugins", "memory_layers"])

    assert rapport["unavailable"] == ["plugins"]
    assert rapport["subsystems"]["memory_layers"]["state"] == DISPONIBLE


def test_un_sous_systeme_inconnu_est_refuse_pas_devine():
    """Un nom mal écrit rendrait « disponible » pour toujours."""
    with pytest.raises(KeyError):
        probe("ce-qui-n-existe-pas")


# ----------------------------------------------------------------------
# 2. Dégradé n'est pas en panne
# ----------------------------------------------------------------------

def test_un_sous_systeme_degrade_n_est_pas_compte_en_panne(monkeypatch):
    """Compter une dégradation comme une panne éteindrait les alertes utiles."""
    monkeypatch.setitem(
        SOUS_SYSTEMES["plugins"], "probe",
        lambda: {"state": DEGRADE, "reason": "bac à sable absent", "detail": {}},
    )

    rapport = degradation_report(["plugins"])

    assert rapport["counts"][DEGRADE] == 1
    assert rapport["counts"][INDISPONIBLE] == 0
    assert rapport["unavailable"] == []


def test_la_connaissance_mondiale_absente_est_degradee_pas_en_panne(monkeypatch):
    """Une référence jamais construite dit pourquoi, et le reste répond."""
    import src.integration.degradation as module

    monkeypatch.setattr(
        "src.knowledge_engine.world.load_world",
        lambda *a, **k: {"built": False, "reason": "Jamais construite.", "countries": []},
    )

    etat = module.probe("world_knowledge")

    assert etat["state"] == DEGRADE
    assert "Jamais construite" in etat["reason"]


def test_le_rapport_dit_que_degrade_n_est_pas_en_panne():
    """La règle est écrite, pas seulement appliquée."""
    regles = " ".join(degradation_report(["memory_layers"])["rules"])

    assert "Dégradé n'est pas en panne" in regles or "n'est pas en panne" in regles


# ----------------------------------------------------------------------
# 3. Ce qui fonctionne encore sans lui
# ----------------------------------------------------------------------

def test_chaque_sous_systeme_dit_ce_qui_marche_sans_lui():
    """« Dégradé » seul ne dit pas s'il faut agir ce soir ou lundi."""
    for nom in SOUS_SYSTEMES:
        etat = probe(nom)

        assert etat["still_works_without"], nom
        assert etat["volet"] > 0, nom


def test_l_orchestration_est_le_seul_dont_l_absence_arrete_le_travail():
    """Le dire évite de traiter dix dégradations comme dix urgences."""
    consequence = probe("orchestration")["still_works_without"]

    assert "arrête le travail principal" in consequence


# ----------------------------------------------------------------------
# 4. L'état réel de ce dépôt, mesuré
# ----------------------------------------------------------------------

def test_tous_les_sous_systemes_repondent_dans_ce_depot():
    """Aucune sonde ne lève sur l'installation réelle."""
    rapport = degradation_report()

    assert rapport["unavailable"] == []
    assert len(rapport["subsystems"]) == len(SOUS_SYSTEMES)


def test_les_sous_systemes_des_vagues_III_a_VI_sont_couverts():
    """C'est l'écart que cette phase referme : ils n'étaient nulle part."""
    couverts = set(SOUS_SYSTEMES)

    assert {"routines", "workflow_checkpoints", "notification_channels",
            "world_knowledge", "knowledge_routing", "plugins",
            "memory_layers", "source_registry", "orchestration"} <= couverts


# ----------------------------------------------------------------------
# 5. Absent et vide ne sont pas la même chose
# ----------------------------------------------------------------------

def test_un_fichier_de_canaux_absent_le_dit():
    """Une liste vide faisait passer « le fichier a disparu » pour « aucun »."""
    from src.services.notification.channels import ChannelRegistry

    rapport = ChannelRegistry(path=Path("/inexistant/canaux.yaml")).channels_report()

    assert "NOT_FOUND" in rapport["declaration"]
    assert rapport["channels"] == []


def test_le_fichier_reel_du_depot_est_nomme():
    """Un exploitant doit savoir quel fichier a été lu."""
    from src.services.notification.channels import ChannelRegistry

    rapport = ChannelRegistry().channels_report()

    assert rapport["declaration"].endswith("channels.yaml")
