"""
Senegal Intelligence Agent for GalSen IA (VOLET 36, ch. D).

ADR-019 gave the base two axes — where knowledge holds (`scope`) and what it is
about (`subject`). This agent applies the one consequence that cannot be left to
retrieval scoring: **on a national subject, no national source means no answer.**

Law, administration and languages do not travel. Answering a Senegalese land
question with foreign law would produce something fluent, plausible and wrong
exactly where being wrong costs the most — someone loses a plot of land. A
refusal that names what is missing is worth more than a confident answer.

**This agent is not the only path to Senegalese knowledge.** Scope-aware
retrieval serves every question; this agent owns the decision to refuse, which
no ranking function should ever own.
"""

from typing import Any, Dict

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.scope import ScopeRefused, parse_subject
from src.knowledge_engine.scoped_retrieval import (
    PORTEE_LOCALE,
    apply_scope_policy,
    scope_notice,
)

#: Le pays de cet agent, tel qu'il est stocké sur les éléments (`country:sn`).
#: Importé de la politique de portée : deux définitions du même pays finiraient
#: par différer, et l'agent refuserait ou accepterait pour de mauvaises raisons.
PORTEE_NATIONALE = PORTEE_LOCALE

#: Nombre d'éléments interrogés. Le tri par portée se fait ensuite : filtrer
#: d'abord sur le pays cacherait le fait qu'il n'y a rien, et rendrait un « rien
#: trouvé » indiscernable d'une base vide.
ELEMENTS_INTERROGES = 10


class SenegalIntelligenceAgent(BaseAgent):
    """Agent qui préfère les sources nationales, et refuse plutôt que de globaliser."""

    agent_id = "senegal"
    required_engines = ("knowledge",)

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Répond avec des sources sénégalaises, ou dit pourquoi il ne répond pas.

        Args:
            context: Contexte d'exécution. `options["subject"]` porte le sujet
                de la question — `law`, `agriculture`, `health`…

        Returns:
            Les éléments retenus **avec leur portée**, ou un refus explicite.
        """
        question = context.request_text().strip()
        if not question:
            return {
                "status": "no_question",
                "reason": "Aucune question dans la demande.",
                "elements": [],
            }

        try:
            sujet = parse_subject(context.options.get("subject"))
        except ScopeRefused as refus:
            # Un sujet mal écrit ne retombe pas sur « non classé » : le refus de
            # `NATIONAL_SUBJECTS` dépend du sujet, et le deviner reviendrait à
            # décider soi-même qu'une question de droit n'en est pas une.
            return {
                "status": "unknown_subject",
                "reason": str(refus),
                "elements": [],
            }

        elements = context.search_knowledge(question, limit=ELEMENTS_INTERROGES)
        if not elements:
            return {
                "status": "empty_base",
                "subject": sujet.value,
                "reason": (
                    "Aucun élément dans la base ne concerne cette question. La base "
                    "est vide sur ce sujet — ce n'est pas une réponse négative."
                ),
                "what_would_settle_it": [
                    f"Ingérer un document déclaré `scope: {PORTEE_NATIONALE}` sur ce "
                    "sujet (`docs/knowledge/README.md`)",
                ],
                "elements": [],
            }

        # L'arbitrage vit dans `scoped_retrieval` (VOLET 35, ch. 04) : cet agent
        # ne réimplémente pas la règle, il l'applique. Une seconde version du
        # refus finirait par refuser dans un cas et pas dans l'autre.
        politique = apply_scope_policy(
            elements, question=question, subject=sujet, scope=PORTEE_NATIONALE,
        )
        rapport = politique["scope_report"]

        if not politique["allowed"]:
            return {
                "status": "no_national_source",
                "subject": sujet.value,
                "reason": politique["reason"],
                "what_would_settle_it": politique["what_would_settle_it"],
                # Les éléments trouvés sont nommés sans être servis : ils
                # existent, ils ne répondent simplement pas à cette question-là.
                "found_but_not_national": [self._resume(item) for item in elements],
                "elements": [],
                "scope_report": rapport,
            }

        return {
            "status": "grounded",
            "subject": sujet.value,
            "national_subject": rapport["national_subject"],
            "elements": [self._resume(item) for item in politique["items"]],
            "national_sources": rapport["local_sources"],
            "global_sources": rapport["global_sources"],
            # La réponse dit sa portée (ch. 05), comme elle dit déjà sa méthode
            # de récupération : un lecteur doit voir qu'une réponse sur le
            # Sénégal a été construite avec des sources sénégalaises — ou non.
            "scope_notice": scope_notice(rapport),
            "scope_report": rapport,
        }

    @staticmethod
    def _portee(item: Dict[str, Any]) -> str:
        """Retourne la portée déclarée d'un élément, « global » par défaut."""
        return str(item.get("scope") or "global")

    def _resume(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Rend un élément avec ce qui permet de le vérifier."""
        return {
            "id": item.get("id"),
            "content": (item.get("content") or "")[:500],
            "scope": self._portee(item),
            "subject": item.get("subject"),
            "status": item.get("status"),
        }


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Question à traiter.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(SenegalIntelligenceAgent, input_data)
