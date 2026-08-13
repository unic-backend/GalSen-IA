"""
Les deux agents du VOLET 36 (ch. D), chacun défini par ce qu'il refuse.

1. **`verifier`** — il peut rendre un verdict « étayé » sans avoir rien lu. Le
   test qui compte est qu'aucun passage donne `cannot_verify`, jamais un verdict
   qui ressemble à un contrôle ayant eu lieu.
2. **`senegal`** — il peut répondre le droit d'un autre pays à une question de
   droit sénégalais. Le test qui compte est le **refus** : fluide, plausible et
   faux est le pire résultat possible sur ces sujets-là.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.senegal.agent import PORTEE_NATIONALE, SenegalIntelligenceAgent  # noqa: E402
from agents.verifier.agent import NON_PRODUIT, FactVerificationAgent  # noqa: E402
from src.agent.context import AgentContext  # noqa: E402

PASSAGE = {
    "id": "k-mil-01",
    "content": (
        "La culture du mil dans le bassin arachidier commence avec les premières "
        "pluies de l'hivernage, entre juin et juillet selon les régions."
    ),
    "scope": "country:sn",
    "subject": "agriculture",
    "status": "approved",
}


class ContexteAvecBase(AgentContext):
    """Contexte dont la base rend ce que le test décide."""

    def __init__(self, elements=None, agent_id="test", **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        self._elements = elements or []

    def search_knowledge(self, query, limit=5, role=None):
        """Rend les éléments décidés par le test."""
        return list(self._elements)


# ----------------------------------------------------------------------
# 1. Le vérificateur de faits
# ----------------------------------------------------------------------

def test_sans_passage_le_verificateur_ne_dit_jamais_etaye():
    """
    Le mode de défaillance nommé au plan.

    Un verdict sans rien derrière est pire qu'une absence de verdict : il a
    l'apparence d'un contrôle qui a eu lieu.
    """
    contexte = ContexteAvecBase(
        elements=[], request="Le rendement du mil atteint quatre tonnes par hectare.",
        agent_id="verifier",
    )

    resultat = FactVerificationAgent().perform(contexte)

    assert resultat["status"] == "cannot_verify"
    assert resultat["claims"][0]["verdict"] == "cannot_verify"
    assert resultat["counts"]["supported"] == 0


def test_le_verificateur_distingue_ce_qui_est_porte_de_ce_qui_est_contredit():
    """
    Trois affirmations, trois verdicts : portée, absente, contredite.

    Une contradiction partage presque tous ses mots avec son passage ; la
    confondre avec un soutien est le défaut que la mesure de polarité empêche.
    """
    contexte = ContexteAvecBase(
        elements=[PASSAGE],
        request=(
            "La culture du mil commence avec les premières pluies de l'hivernage. "
            "Le rendement moyen atteint quatre tonnes par hectare. "
            "La culture du mil ne commence pas avec les pluies de l'hivernage."
        ),
        agent_id="verifier",
    )

    resultat = FactVerificationAgent().perform(contexte)
    comptes = resultat["counts"]

    assert comptes["supported"] == 1
    assert comptes["unsupported"] == 1
    assert comptes["disputed"] == 1


def test_le_verificateur_ne_reecrit_jamais_la_reponse():
    """
    Son contrat : il mesure, il ne corrige pas.

    Mélanger la mesure et la correction rendrait impossible de savoir, à la
    lecture suivante, laquelle des deux on lit.
    """
    contexte = ContexteAvecBase(
        elements=[PASSAGE],
        request="Le rendement moyen atteint quatre tonnes par hectare.",
        agent_id="verifier",
    )

    resultat = FactVerificationAgent().perform(contexte)

    assert "rewritten" not in resultat and "corrected_answer" not in resultat
    assert resultat["not_produced"] == list(NON_PRODUIT)
    assert resultat["unavailable"], "Le verdict ne dit pas ce qu'il ne sait pas mesurer"


def test_le_verificateur_accepte_des_affirmations_deja_decoupees():
    """L'appelant qui a déjà ses affirmations n'a pas à les recoller en texte."""
    contexte = ContexteAvecBase(
        elements=[PASSAGE], request="peu importe", agent_id="verifier",
        options={"claims": ["La culture du mil commence avec les premières pluies."]},
    )

    resultat = FactVerificationAgent().perform(contexte)

    assert len(resultat["claims"]) == 1
    assert resultat["claims"][0]["verdict"] == "supported"


# ----------------------------------------------------------------------
# 2. L'agent Sénégal
# ----------------------------------------------------------------------

def test_une_question_de_droit_sans_source_nationale_est_refusee():
    """
    Le test qui justifie cet agent.

    Des éléments existent, ils sont même pertinents lexicalement — et aucun ne
    vaut pour le Sénégal. Répondre avec eux donnerait une réponse fluide,
    plausible et fausse là où elle coûte un terrain.
    """
    mondial = dict(PASSAGE, id="k-droit-01", scope="global", subject="law",
                   content="Le droit foncier distingue la propriété et l'usage.")
    contexte = ContexteAvecBase(
        elements=[mondial],
        request="Comment immatriculer un terrain du domaine national ?",
        agent_id="senegal", options={"subject": "law"},
    )

    resultat = SenegalIntelligenceAgent().perform(contexte)

    assert resultat["status"] == "no_national_source"
    assert resultat["elements"] == [], "Un élément mondial a été servi malgré le refus"
    assert resultat["found_but_not_national"], "Le refus cache ce qui a pourtant été trouvé"
    assert resultat["what_would_settle_it"]


def test_une_base_vide_le_dit_au_lieu_de_repondre_non():
    """« Je n'ai rien » n'est pas « la réponse est non »."""
    contexte = ContexteAvecBase(
        elements=[], request="Quel est le délai de préavis légal ?",
        agent_id="senegal", options={"subject": "law"},
    )

    resultat = SenegalIntelligenceAgent().perform(contexte)

    assert resultat["status"] == "empty_base"
    assert resultat["what_would_settle_it"]


def test_une_source_nationale_est_servie_avec_sa_portee():
    """Un élément servi porte sa portée : sinon personne ne peut la vérifier."""
    contexte = ContexteAvecBase(
        elements=[PASSAGE], request="Quand semer le mil ?",
        agent_id="senegal", options={"subject": "agriculture"},
    )

    resultat = SenegalIntelligenceAgent().perform(contexte)

    assert resultat["status"] == "grounded"
    assert resultat["elements"][0]["scope"] == PORTEE_NATIONALE
    assert resultat["national_sources"] == 1


def test_un_sujet_non_national_accepte_une_source_mondiale_sans_la_deguiser():
    """
    L'agronomie du mil voyage ; le droit non.

    Servir un élément mondial est permis ici — mais jamais silencieusement : sa
    portée est rendue avec lui.
    """
    mondial = dict(PASSAGE, id="k-agro-01", scope="global",
                   content="Le mil est une céréale résistante à la sécheresse.")
    contexte = ContexteAvecBase(
        elements=[mondial], request="Le mil résiste-t-il à la sécheresse ?",
        agent_id="senegal", options={"subject": "agriculture"},
    )

    resultat = SenegalIntelligenceAgent().perform(contexte)

    assert resultat["status"] == "grounded"
    assert resultat["elements"][0]["scope"] == "global"
    assert resultat["national_sources"] == 0


def test_un_sujet_mal_ecrit_ne_retombe_pas_sur_non_classe():
    """
    Deviner le sujet reviendrait à décider qu'une question de droit n'en est
    pas une — donc à supprimer le refus qui protège la réponse.
    """
    contexte = ContexteAvecBase(
        elements=[PASSAGE], request="Quel est le délai de préavis ?",
        agent_id="senegal", options={"subject": "droit"},
    )

    resultat = SenegalIntelligenceAgent().perform(contexte)

    assert resultat["status"] == "unknown_subject"
    assert resultat["elements"] == []


# ----------------------------------------------------------------------
# Le registre
# ----------------------------------------------------------------------

def test_les_deux_agents_sont_declares_au_registre():
    """Un agent absent du registre n'est joignable par aucun chemin."""
    import yaml

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "agents", "registry.yaml"), encoding="utf-8") as fichier:
        registre = yaml.safe_load(fichier)

    declares = {agent["id"]: agent for agent in registre["agents"]}
    for agent_id in ("verifier", "senegal"):
        assert agent_id in declares, f"« {agent_id} » absent de agents/registry.yaml"
        assert declares[agent_id]["enabled"] is True
        assert declares[agent_id]["module"] == f"agents.{agent_id}.agent"


@pytest.mark.parametrize("agent_id", ["verifier", "senegal"])
def test_les_deux_agents_repondent_par_leur_point_d_entree(agent_id):
    """Le point d'entrée historique est ce que le répartiteur appelle."""
    import importlib

    module = importlib.import_module(f"agents.{agent_id}.agent")
    resultat = module.execute("Le mil se sème avec les premières pluies.")

    assert resultat["agent"] == agent_id
    assert resultat["status"] == "success", resultat.get("error")


def test_un_agent_recoit_desormais_la_portee_reelle_des_elements(tmp_path, monkeypatch):
    """
    Le chaînon qui manquait, vérifié sur un vrai moteur.

    Sans les deux axes de l'ADR-019 dans ce qu'un agent lit, `senegal` ne
    pourrait pas distinguer une source nationale d'une source mondiale — il
    servirait du droit d'ailleurs sans jamais le voir.
    """
    from src.integration.engine_registry import get_shared_registry
    from src.knowledge_engine.scope import KnowledgeSubject
    from src.knowledge_engine.types import KnowledgeItem

    # Le moteur de connaissances est partagé par le processus : l'élément est
    # retrouvé par son identifiant, pas par sa position — les autres tests en
    # ajoutent aussi.
    base = get_shared_registry().get("knowledge")
    identifiant = base.add_knowledge(KnowledgeItem(
        content="Le domaine national sénégalais est régi par une loi propre au pays.",
        scope="country:sn",
        subject=KnowledgeSubject.LAW,
    ))
    try:
        contexte = AgentContext(request="domaine national", agent_id="senegal")
        elements = contexte.search_knowledge("domaine national sénégalais", limit=10)

        porte = [element for element in elements if element["id"] == identifiant]
        assert porte, "La base ne rend pas l'élément : le test ne mesure plus les axes"
        assert porte[0]["scope"] == "country:sn"
        assert porte[0]["subject"] == "law"
    finally:
        base.delete_knowledge(identifiant)
