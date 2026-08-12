"""
Opportunity Analyst Agent for GalSen IA (VOLET 34, ch. 11).

The brief asks for a "business opportunity analyst". This is the most dangerous
agent in the whole VOLET, and the danger is not technical.

An agent asked *"is there an opportunity in solar irrigation in Senegal?"* can
always produce a confident, well-structured, entirely invented answer: a market
size, a growth rate, three competitors, a recommendation. Nothing in the platform
would contradict it, and someone might spend money on it.

`.claude/rules/verification.md` already names this failure — a test once pinned
`result[0]["title"] == "Réunion d'équipe"` for a meeting nobody scheduled — and
`docs/knowledge/README.md` refuses an invented corpus for the same reason:
*serving invented claims to a farmer would be the worst possible use of this
repository.*

## The rule this agent is built on

**Every statement carries its source, or it is not made.**

- It reports **signals**, each attached to a knowledge entry or a web result
  with its origin. A finding whose source cannot be named is dropped, counted,
  and the count is reported.
- With no sourced signal, the answer is `insufficient_evidence` — never a
  cautious-sounding paragraph that reads like an analysis.
- It produces **no market size, no growth rate, no revenue projection**. Those
  would come from nowhere. What it refuses is listed in the output so the
  absence reads as a decision rather than an oversight.
- "Signal" is not "opportunity". The wording is deliberate: the agent surfaces
  what the sources say, and leaves the conclusion to a human who can weigh it.
"""

from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module

#: Ce que cet agent ne produira pas, quelle que soit la demande. Énuméré dans la
#: réponse : une absence expliquée vaut mieux qu'une absence remarquée.
NON_PRODUIT = (
    "taille de marché : aucune source de la plateforme n'en porte",
    "taux de croissance : il se calculerait sur des chiffres absents",
    "projection de revenus : elle serait une invention présentée comme un calcul",
    "recommandation d'investir : elle appartient à une personne, pas à un agent",
)

#: Nombre de sources distinctes à partir duquel un signal est dit corroboré. Deux
#: n'est pas un seuil statistique — c'est la différence entre « quelqu'un l'a
#: écrit » et « deux sources indépendantes le disent », et elle est rendue telle
#: quelle plutôt que convertie en score.
SOURCES_POUR_CORROBORER = 2


class OpportunityAnalystAgent(BaseAgent):
    """Agent qui rapporte des signaux sourcés, et refuse de conclure sans source."""

    agent_id = "opportunity"
    required_engines = ("knowledge", "tool", "memory")

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Rassemble les signaux sourcés qui concernent la demande.

        Args:
            context: Contexte d'exécution.

        Returns:
            Les signaux trouvés avec leurs sources, ou l'état d'insuffisance.
        """
        sujet = context.request_text().strip()
        if not sujet:
            return {
                "status": "no_subject",
                "reason": "Aucun sujet dans la demande : il n'y a rien à documenter.",
                "signals": [],
            }

        signaux: List[Dict[str, Any]] = []
        sans_source = 0

        for element in context.search_knowledge(sujet, limit=10):
            signal = self._depuis_connaissance(element)
            if signal is None:
                sans_source += 1
                continue
            signaux.append(signal)

        for resultat in context.search_web(sujet, max_results=5):
            signal = self._depuis_web(resultat)
            if signal is None:
                sans_source += 1
                continue
            signaux.append(signal)

        if not signaux:
            return {
                "status": "insufficient_evidence",
                "subject": sujet,
                "reason": (
                    "Aucune source ne documente ce sujet : ni la base de "
                    "connaissances ni la recherche web n'ont rendu de résultat "
                    "attribuable."
                ),
                "what_would_settle_it": [
                    "Ingérer des documents déclarés sur ce sujet "
                    "(`docs/knowledge/README.md`)",
                    "Activer l'outil de recherche web, s'il est désactivé",
                ],
                "dropped_unsourced": sans_source,
                "signals": [],
                "not_produced": list(NON_PRODUIT),
            }

        origines = {signal["source"]["origin"] for signal in signaux}
        return {
            "status": "grounded",
            "subject": sujet,
            "signal_count": len(signaux),
            "signals": signaux,
            "distinct_origins": sorted(origines),
            # « Corroboré » veut dire : plusieurs origines distinctes le disent.
            # Rien de plus, et surtout pas « c'est vrai ».
            "corroborated": len(origines) >= SOURCES_POUR_CORROBORER,
            "dropped_unsourced": sans_source,
            "not_produced": list(NON_PRODUIT),
            "note": (
                "Ce sont des signaux sourcés, pas une opportunité établie. La "
                "conclusion revient à une personne qui peut peser les sources."
            ),
        }

    @staticmethod
    def _depuis_connaissance(element: Dict[str, Any]) -> Any:
        """
        Convertit une connaissance en signal, ou l'écarte faute d'attribution.

        Une connaissance sans identifiant ne peut pas être retrouvée : la citer
        reviendrait à affirmer sans permettre la vérification.
        """
        identifiant = element.get("id")
        contenu = (element.get("content") or "").strip()
        if not identifiant or not contenu:
            return None
        return {
            "statement": contenu[:500],
            "source": {
                "origin": "knowledge",
                "reference": identifiant,
                "status": element.get("status"),
                "domain": element.get("domain"),
            },
            "confidence_reported_by_source": element.get("confidence"),
        }

    @staticmethod
    def _depuis_web(resultat: Dict[str, Any]) -> Any:
        """Convertit un résultat web en signal, ou l'écarte faute d'URL."""
        if not isinstance(resultat, dict):
            return None
        url = resultat.get("url") or resultat.get("link")
        titre = (resultat.get("title") or resultat.get("snippet") or "").strip()
        if not url or not titre:
            return None
        return {
            "statement": titre[:500],
            "source": {"origin": "web", "reference": url},
            # Aucune confiance n'est attribuée à un résultat web : la plateforme
            # n'a aucun moyen d'évaluer la fiabilité d'un site, et un score
            # inventé serait pris pour une mesure.
            "confidence_reported_by_source": None,
        }


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(OpportunityAnalystAgent, input_data)
