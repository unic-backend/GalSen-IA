"""
Manques, sources candidates et contradictions (VOLET 35, ch. 06, 07 et 09).

Les trois chapitres de l'autonomie, et chacun est défini par ce qu'il **ne**
fait pas :

- **06** — un manque est mesuré sur de vraies questions. Un manque que personne
  n'a jamais demandé n'est pas un manque, c'est une supposition sur l'avenir.
- **07** — les candidats viennent du registre, jamais d'une recherche libre.
  Proposer n'est pas décider, et « cherche sur internet et apprends » est la
  façon la plus rapide de remplir une base d'absurdités confiantes.
- **09** — une contradiction est **rapportée**, jamais résolue. Le plus récent
  n'est pas automatiquement le bon.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.contradictions import NON_DETECTE, detect_contradictions  # noqa: E402
from src.knowledge_engine.gaps import SEUIL_DE_MANQUE, detect_gaps  # noqa: E402
from src.knowledge_engine.source_discovery import (  # noqa: E402
    propose_for_gap,
    propose_for_gaps,
)
from src.proactive.detectors import DETECTEURS, manques_de_connaissance  # noqa: E402


class AuditFictif:
    """Audit qui rend les recherches décidées par le test."""

    def __init__(self, recherches):
        """Construit l'audit depuis `(question, nombre de résultats)`."""
        self._evenements = [
            type("Evenement", (), {
                "metadata": {"query": question, "results_count": resultats},
                "user_request": question,
            })()
            for question, resultats in recherches
        ]

    def list_events(self, limit=100, **filtres):
        """Rend les événements, comme le moteur d'audit réel."""
        return self._evenements[:limit]


# ----------------------------------------------------------------------
# Chapitre 06 — le manque est mesuré, pas imaginé
# ----------------------------------------------------------------------

def test_un_manque_est_un_couple_sujet_portee_reellement_demande():
    """Deux questions sans réponse sur le même couple : c'est un usage, pas un accident."""
    audit = AuditFictif([
        ("Quelles variétés de mil à Kaolack ?", 0),
        ("Quel semis de mil à Thiès ?", 0),
    ])

    rapport = detect_gaps(audit=audit)

    assert len(rapport["gaps"]) == 1
    manque = rapport["gaps"][0]
    assert manque["subject"] == "agriculture"
    assert manque["scope"] == "country:sn"
    assert manque["unanswered"] == 2


def test_une_seule_question_sans_reponse_ne_fait_pas_un_manque():
    """
    Une recherche unique et malheureuse arrive. Bâtir une priorité dessus
    reviendrait à confondre un accident avec un besoin.
    """
    audit = AuditFictif([("Quelles variétés de mil à Kaolack ?", 0)])

    rapport = detect_gaps(audit=audit)

    assert rapport["gaps"] == []
    assert rapport["threshold"] == SEUIL_DE_MANQUE


def test_une_question_servie_n_est_pas_un_manque():
    """Le signal est l'absence de résultat, pas la présence d'une question."""
    audit = AuditFictif([
        ("Quelles variétés de mil à Kaolack ?", 3),
        ("Quel semis de mil à Thiès ?", 2),
    ])

    rapport = detect_gaps(audit=audit)

    assert rapport["gaps"] == []
    assert rapport["covered"], "Un couple servi devrait apparaître comme couvert"


def test_le_module_n_invente_aucun_manque_sans_question():
    """
    Le cœur du chapitre : sans question réelle, il n'y a rien à signaler — et
    `measured_questions: 0` n'est pas « aucun manque ».
    """
    rapport = detect_gaps(audit=AuditFictif([]))

    assert rapport["gaps"] == []
    assert rapport["measured_questions"] == 0


def test_les_exemples_sont_de_vraies_questions():
    """Un manque illustré par une question inventée serait invérifiable."""
    audit = AuditFictif([
        ("Quelle loi foncière à Dakar ?", 0),
        ("Quelle loi sur le foncier à Ziguinchor ?", 0),
    ])

    manque = detect_gaps(audit=audit)["gaps"][0]

    assert "Dakar" in manque["examples"][0] or "Ziguinchor" in manque["examples"][0]


# ----------------------------------------------------------------------
# Chapitre 07 — proposer, sans décider
# ----------------------------------------------------------------------

def test_les_candidats_viennent_du_registre_et_de_nulle_part_ailleurs():
    """« Cherche sur internet et apprends » n'est ni fait, ni proposé."""
    from src.knowledge_engine.source_registry import known_sources

    proposition = propose_for_gap("agriculture", "country:sn")
    inscrits = {source["name"] for source in known_sources()}

    assert proposition["candidates"], "Aucun candidat pour un sujet couvert par le registre"
    assert proposition["source_of_candidates"] == "registry"
    for candidat in proposition["candidates"]:
        assert candidat["name"] in inscrits


def test_la_proposition_ne_decide_rien():
    """
    Ajouter une autorité est une décision humaine, et c'est elle qui donne au
    registre sa valeur.
    """
    proposition = propose_for_gap("law", "country:sn")

    assert proposition["decides_nothing"] is True
    assert "ingested" not in proposition and "collected" not in proposition


def test_les_sources_de_la_portee_demandee_passent_devant():
    """Pour un manque sénégalais, une institution du pays passe avant une mondiale."""
    candidats = propose_for_gap("agriculture", "country:sn")["candidates"]

    assert candidats[0]["scope"] == "country:sn"
    assert any(candidat["scope"] == "global" for candidat in candidats)


def test_un_sujet_que_le_registre_ne_couvre_pas_dit_quoi_faire():
    """
    Aucun candidat n'est une réponse en soi : le rapport dit alors ce qui
    trancherait, et rappelle qu'aucune recherche libre n'est faite.
    """
    proposition = propose_for_gap("history", "country:sn")
    proposition_vide = propose_for_gap("engineering", "country:sn")

    assert proposition["candidates"], "L'IFAN devrait couvrir l'histoire sénégalaise"
    assert proposition_vide["candidates"] == []
    assert any("registre" in ligne for ligne in proposition_vide["what_would_settle_it"])


def test_la_proposition_suit_une_mesure():
    """L'entrée vient de `detect_gaps()` : jamais une intuition sur ce qui manquerait."""
    audit = AuditFictif([
        ("Quelles variétés de mil à Kaolack ?", 0),
        ("Quel semis de mil à Thiès ?", 0),
    ])
    manques = detect_gaps(audit=audit)["gaps"]

    propositions = propose_for_gaps(manques)

    assert len(propositions) == len(manques)
    assert propositions[0]["subject"] == "agriculture"


# ----------------------------------------------------------------------
# Chapitre 09 — rapporter, jamais résoudre
# ----------------------------------------------------------------------

CHIFFRE_A = {"id": "k1", "scope": "country:sn", "subject": "economics",
             "content": "La production de mil a atteint 125000 tonnes en 2022."}
CHIFFRE_B = {"id": "k2", "scope": "country:sn", "subject": "economics",
             "content": "La production de mil a atteint 131500 tonnes en 2022."}
NIE = {"id": "k3", "scope": "country:sn", "subject": "law",
       "content": "Le domaine national n'est pas cessible."}
AFFIRME = {"id": "k4", "scope": "country:sn", "subject": "law",
           "content": "Le domaine national est cessible."}
AUTRE_PAYS = {"id": "k5", "scope": "global", "subject": "law",
              "content": "Le domaine national est cessible."}


def test_un_desaccord_de_chiffres_est_repere():
    """Le désaccord le plus fréquent d'une base statistique, et le plus cité de travers."""
    rapport = detect_contradictions([CHIFFRE_A, CHIFFRE_B])

    assert rapport["by_type"]["numeric"] == 1
    conflit = rapport["contradictions"][0]
    assert {conflit["left"]["id"], conflit["right"]["id"]} == {"k1", "k2"}


def test_un_desaccord_de_polarite_est_repere():
    """L'un nie ce que l'autre affirme, avec les mêmes mots."""
    rapport = detect_contradictions([NIE, AFFIRME])

    assert rapport["by_type"]["polarity"] == 1


def test_deux_pays_ne_se_contredisent_pas():
    """
    Comparer une loi sénégalaise à une loi d'ailleurs produirait un conflit
    permanent que personne ne pourrait résoudre — parce qu'il n'en est pas un.
    """
    rapport = detect_contradictions([NIE, AUTRE_PAYS])

    assert rapport["contradictions"] == []


def test_rien_n_est_resolu_ni_modifie():
    """
    Le cœur du chapitre : aucun gagnant n'est désigné. Un champ « vainqueur »
    serait lu comme une conclusion, et personne ne rouvrirait le couple.
    """
    elements = [dict(CHIFFRE_A), dict(CHIFFRE_B)]
    rapport = detect_contradictions(elements)

    assert rapport["resolved"] == 0
    assert "winner" not in str(rapport)
    assert elements == [CHIFFRE_A, CHIFFRE_B], "La mesure a modifié ce qu'elle lisait"
    assert rapport["contradictions"][0]["resolution"].startswith("Aucune")


def test_la_methode_et_ses_angles_morts_sont_nommes():
    """Ce que la détection ne voit pas est écrit, pas sous-entendu."""
    rapport = detect_contradictions([CHIFFRE_A, CHIFFRE_B])

    assert rapport["method"] == "lexical"
    assert rapport["not_detected"] == list(NON_DETECTE)


def test_deux_passages_sans_rapport_ne_sont_pas_un_conflit():
    """Sous le seuil de recouvrement, un désaccord de polarité ne veut rien dire."""
    sans_rapport = {"id": "k6", "scope": "country:sn", "subject": "economics",
                    "content": "Le taux de change du franc CFA reste fixe."}

    rapport = detect_contradictions([CHIFFRE_A, sans_rapport])

    assert rapport["contradictions"] == []


# ----------------------------------------------------------------------
# Le détecteur proactif
# ----------------------------------------------------------------------

def test_le_detecteur_de_manques_est_declare_et_silencieux_sans_question():
    """
    Sans question mesurée, il n'y a rien à dire — et il ne dit rien.

    L'audit est injecté vide : le journal réel est **partagé par le processus**,
    et les recherches des autres tests y laissent de vraies traces. Lire le
    journal partagé ici mesurerait la suite de tests, pas le détecteur.
    """
    assert DETECTEURS["knowledge_gaps"] is manques_de_connaissance
    assert manques_de_connaissance(audit=AuditFictif([])) == []


def test_le_detecteur_de_manques_propose_des_sources_sans_rien_collecter(monkeypatch):
    """Quand il parle, il porte les candidats du registre et dit que rien n'a été pris."""
    from src.knowledge_engine import gaps as module_gaps

    audit = AuditFictif([
        ("Quelles variétés de mil à Kaolack ?", 0),
        ("Quel semis de mil à Thiès ?", 0),
    ])
    monkeypatch.setattr(module_gaps, "_evenements", lambda *a, **k: audit.list_events())

    trouvees = manques_de_connaissance(audit=audit)

    assert len(trouvees) == 1
    observation = trouvees[0].to_dict()
    assert observation["evidence"]["gaps"][0]["candidate_sources"]
    assert "rien n'a été collecté" in observation["suggested_action"].lower()


@pytest.mark.parametrize("module", ["gaps", "source_discovery", "contradictions"])
def test_aucun_de_ces_modules_ne_visite_le_web(module):
    """
    La collecte est le chapitre 08 — sous approbation, licence vérifiée,
    `robots.txt` respecté. Aucun de ces trois modules ne télécharge quoi que ce
    soit, et ce test le garde.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = os.path.join(racine, "src", "knowledge_engine", f"{module}.py")
    with open(chemin, encoding="utf-8") as fichier:
        source = fichier.read()

    for interdit in ("requests.", "urlopen", "urlretrieve", "httpx."):
        assert interdit not in source, f"« {module} » atteint le réseau via {interdit}"
