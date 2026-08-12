"""
Le geste passe par le portillon, ou il n'a pas lieu (VOLET 34, ch. 06).

Le chapitre 05 a donné des yeux ; celui-ci donne une main. La règle qui tient
tout le reste vient d'ADR-017 §4 : **une action nomme sa cible, ou elle est
refusée**. Une demande d'approbation qui dit « cliquer en (412, 380) » ne peut
pas être évaluée par l'humain qui la reçoit.

Le chemin est celui de `GuardedEditor` (VOLET 31) — proposer, décider, appliquer
— repris à l'identique pour ne pas avoir deux portillons qui divergeraient.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.approval_engine.approval_manager import ApprovalManagerImpl  # noqa: E402
from src.tools.gui import (  # noqa: E402
    ActionKind,
    ApprovalRequired,
    GUIAction,
    GUIBackend,
    GUITool,
    GUIUnavailable,
)
from src.tools.screen.types import ScreenElement  # noqa: E402


class MainDeTest(GUIBackend):
    """Exécutant en mémoire : il enregistre les gestes au lieu de les faire."""

    name = "test"

    def __init__(self, indisponible=None):
        self.indisponible = indisponible
        self.gestes = []

    def unavailable_reason(self):
        return self.indisponible

    def click(self, element, double=False):
        self.gestes.append(("double_click" if double else "click", element.label))

    def type_text(self, element, text):
        self.gestes.append(("type", element.label, text))

    def press(self, key, element=None):
        self.gestes.append(("press", key, element.label if element else None))


class ContexteDeTest:
    """
    Contexte minimal : un vrai moteur d'approbation, pas une imitation.

    Le portillon est ce qui est éprouvé ici ; le simuler ferait passer le test
    sur un objet qui n'est pas celui qui protège la plateforme.
    """

    def __init__(self, avec_portillon=True):
        self.approval = ApprovalManagerImpl() if avec_portillon else None
        self.audits = []

    def submit_approval(self, action, description, metadata=None):
        from src.approval_engine.types import ApprovalRequest

        return self.approval.submit(ApprovalRequest(
            agent_id="gui", request_id="req_test", action=action,
            description=description, metadata=metadata or {},
        ))

    def record_audit(self, event_type, action, **kwargs):
        self.audits.append((action, kwargs))


@pytest.fixture
def bouton():
    """Un bouton identifié, actif, situé."""
    return ScreenElement(role="button", label="Enregistrer", bounds=(10, 20, 80, 24),
                         application="Éditeur")


@pytest.fixture
def outil():
    """Outil avec portillon réel et main de test."""
    contexte = ContexteDeTest()
    main = MainDeTest()
    return GUITool(context=contexte, backends=[main]), contexte, main


def _action(cible, **kwargs):
    """Construit une action de clic avec une raison."""
    defauts = {"kind": ActionKind.CLICK, "target": cible, "reason": "enregistrer le document"}
    return GUIAction(**{**defauts, **kwargs})


# ----------------------------------------------------------------------
# Rien ne bouge sans décision humaine
# ----------------------------------------------------------------------

def test_proposer_n_execute_rien(outil, bouton):
    """C'est la propriété centrale : proposer n'est pas agir."""
    gui, _, main = outil

    resultat = gui.execute("propose", _action(bouton))

    assert resultat["status"] == "pending_approval"
    assert resultat["approval_request_id"]
    assert main.gestes == []


def test_appliquer_sans_approbation_est_refuse(outil, bouton):
    """Une demande en attente n'autorise rien."""
    gui, _, main = outil
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]

    with pytest.raises(ApprovalRequired, match="pending"):
        gui.execute("apply", demande)

    assert main.gestes == []


def test_un_geste_approuve_s_execute(outil, bouton):
    """Le contre-test : le portillon ne doit pas tout bloquer."""
    gui, contexte, main = outil
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]
    contexte.approval.approve(demande, decided_by="awa")

    resultat = gui.execute("apply", demande)

    assert resultat["status"] == "done"
    assert main.gestes == [("click", "Enregistrer")]


def test_une_approbation_ne_sert_qu_une_fois(outil, bouton):
    """
    Rejouer un identifiant approuvé permettrait de cliquer deux fois avec une
    seule décision — et le second clic n'aurait été approuvé par personne.
    """
    gui, contexte, main = outil
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]
    contexte.approval.approve(demande)
    gui.execute("apply", demande)

    with pytest.raises(ApprovalRequired, match="inconnue"):
        gui.execute("apply", demande)

    assert len(main.gestes) == 1


def test_un_geste_rejete_ne_s_execute_pas(outil, bouton):
    """Un refus humain doit peser autant qu'une approbation."""
    gui, contexte, main = outil
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]
    contexte.approval.reject(demande, reason="pas maintenant")

    with pytest.raises(ApprovalRequired):
        gui.execute("apply", demande)

    assert main.gestes == []


def test_sans_portillon_l_outil_ferme(bouton):
    """
    Ailleurs, un moteur absent dégrade proprement. Ici il ferme : un portillon
    qu'on peut faire disparaître n'est pas un portillon (VOLET 31).
    """
    gui = GUITool(context=ContexteDeTest(avec_portillon=False), backends=[MainDeTest()])

    resultat = gui.execute("propose", _action(bouton))

    assert resultat["status"] == "refused"
    assert "approbation" in resultat["detail"].lower()


# ----------------------------------------------------------------------
# Une action nomme sa cible, ou elle est refusée
# ----------------------------------------------------------------------

def test_une_action_sans_cible_est_refusee(outil):
    """ADR-017 §4 : rien à nommer, donc rien à approuver."""
    gui, _, _ = outil

    resultat = gui.execute("propose", GUIAction(kind=ActionKind.CLICK, reason="cliquer"))

    assert resultat["status"] == "refused"
    assert "cible" in resultat["detail"].lower()


def test_une_cible_sans_libelle_ni_identifiant_est_refusee(outil):
    """La demande d'approbation serait illisible, donc non évaluable."""
    gui, _, _ = outil
    anonyme = ScreenElement(role="button", bounds=(0, 0, 10, 10))

    resultat = gui.execute("propose", _action(anonyme))

    assert resultat["status"] == "refused"
    assert "libellé" in resultat["detail"]


def test_une_cible_sans_position_est_refusee(outil):
    """On ne peut pas agir sur ce qu'on ne sait pas situer."""
    gui, _, _ = outil
    sans_bornes = ScreenElement(role="button", label="Enregistrer")

    assert gui.execute("propose", _action(sans_bornes))["status"] == "refused"


def test_un_element_desactive_est_refuse(outil):
    """Le geste ne ferait rien, et serait rapporté comme fait."""
    gui, _, _ = outil
    eteint = ScreenElement(role="button", label="Supprimer", bounds=(1, 2, 3, 4),
                           enabled=False)

    resultat = gui.execute("propose", _action(eteint))

    assert resultat["status"] == "refused"
    assert "désactivé" in resultat["detail"]


def test_une_action_sans_raison_est_refusee(outil, bouton):
    """Un humain doit décider sans reconstituer l'intention de l'agent."""
    gui, _, _ = outil

    resultat = gui.execute("propose", _action(bouton, reason="  "))

    assert resultat["status"] == "refused"
    assert "raison" in resultat["detail"].lower()


def test_la_demande_soumise_nomme_la_cible(outil, bouton):
    """Ce que l'humain lira doit contenir le libellé, pas des coordonnées."""
    gui, contexte, _ = outil
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]

    description = contexte.approval.get(demande).description

    assert "Enregistrer" in description
    assert "enregistrer le document" in description


# ----------------------------------------------------------------------
# Les secrets ne passent pas par un agent
# ----------------------------------------------------------------------

def test_une_saisie_dans_un_champ_de_mot_de_passe_est_refusee(outil):
    """
    Le portillon protège l'action, pas la valeur. Un identifiant qui transite par
    un agent est un problème d'identifiants, qu'une approbation ne résout pas.
    """
    gui, _, _ = outil
    champ = ScreenElement(role="password", label="Mot de passe", bounds=(1, 2, 3, 4))

    resultat = gui.execute(
        "propose", _action(champ, kind=ActionKind.TYPE, text="secret-tres-confidentiel")
    )

    assert resultat["status"] == "refused"
    assert "secret" in resultat["detail"].lower()


def test_le_texte_saisi_n_entre_ni_dans_la_demande_ni_dans_l_audit(outil):
    """
    L'audit persiste depuis cette semaine : un texte conservé là serait une fuite
    qui survit au redémarrage. Seule sa longueur est enregistrée.
    """
    gui, contexte, _ = outil
    champ = ScreenElement(role="text", label="Recherche", bounds=(1, 2, 3, 4))
    action = _action(champ, kind=ActionKind.TYPE, text="mil sénégalais")

    demande = gui.execute("propose", action)["approval_request_id"]
    contexte.approval.approve(demande)
    gui.execute("apply", demande)

    enregistre = str(contexte.approval.get(demande).metadata) + str(contexte.audits)
    assert "mil sénégalais" not in enregistre
    assert "text_length" in enregistre


# ----------------------------------------------------------------------
# Disponibilité, et refus qui nomment leur raison
# ----------------------------------------------------------------------

def test_l_etat_repond_meme_sans_main_ni_portillon():
    """Un agent doit pouvoir constater qu'il n'a pas de main, pas le déduire."""
    etat = GUITool().execute("availability")

    assert etat["can_act"] is False
    assert etat["approval_gate"] is False


def test_sur_cette_machine_les_raisons_sont_nommees():
    """Mesuré ici : pas de session graphique, et les backends le disent."""
    etat = GUITool(context=ContexteDeTest()).execute("availability")

    raisons = " ".join(ligne["reason"] for ligne in etat["backends"])
    assert "session graphique" in raisons or "vise Windows" in raisons


def test_sans_executant_un_geste_approuve_refuse_franchement(bouton):
    """
    Rapporter « fait » sans exécutant serait le pire des comptes rendus : un
    geste approuvé, jamais accompli, et déclaré accompli.
    """
    contexte = ContexteDeTest()
    gui = GUITool(context=contexte, backends=[MainDeTest(indisponible="pas d'écran")])
    demande = gui.execute("propose", _action(bouton))["approval_request_id"]
    contexte.approval.approve(demande)

    with pytest.raises(GUIUnavailable, match="pas d'écran"):
        gui.execute("apply", demande)


def test_un_identifiant_jamais_propose_est_refuse(outil):
    """Aucun geste ne s'exécute sur un identifiant que cet outil n'a pas émis."""
    gui, _, _ = outil

    with pytest.raises(ApprovalRequired, match="inconnue"):
        gui.execute("apply", "appr_invente")


def test_lire_et_agir_restent_deux_outils():
    """
    La séparation est la garantie : un agent peut recevoir la vue sans recevoir
    le geste. Si `ScreenTool` gagnait un clic, elle disparaîtrait.
    """
    from src.tools.screen import ScreenTool

    assert set(ScreenTool().available_operations()) == {"availability", "find", "snapshot"}
    assert set(GUITool().available_operations()) == {"apply", "availability", "propose"}
