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

from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.scope import (
    KnowledgeScope,
    ScopeRefused,
    parse_subject,
    requires_national_source,
)

#: Le pays de cet agent. La portée est comparée à sa forme textuelle, celle qui
#: est réellement stockée sur les éléments (`country:sn`).
PORTEE_NATIONALE = str(KnowledgeScope.country_("SN"))

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
        nationaux = [item for item in elements if self._portee(item) == PORTEE_NATIONALE]
        national_exige = requires_national_source(sujet)

        if not elements:
            return {
                "status": "empty_base",
                "subject": sujet.value,
                "reason": (
                    "Aucun élément dans la base ne concerne cette question. La base "
                    "est vide sur ce sujet — ce n'est pas une réponse négative."
                ),
                "what_would_settle_it": self._ce_qui_trancherait(sujet, national_exige),
                "elements": [],
            }

        if national_exige and not nationaux:
            return {
                "status": "no_national_source",
                "subject": sujet.value,
                "reason": (
                    f"« {sujet.value} » ne se transporte pas d'un pays à l'autre : "
                    f"{len(elements)} élément(s) trouvé(s), aucun de portée "
                    f"« {PORTEE_NATIONALE} ». Répondre avec de la connaissance "
                    "mondiale donnerait une réponse fluide, plausible et fausse."
                ),
                "what_would_settle_it": self._ce_qui_trancherait(sujet, national_exige),
                # Les éléments trouvés sont nommés sans être servis : ils
                # existent, ils ne répondent simplement pas à cette question-là.
                "found_but_not_national": [self._resume(item) for item in elements],
                "elements": [],
            }

        retenus = nationaux if nationaux else elements
        return {
            "status": "grounded",
            "subject": sujet.value,
            "national_subject": national_exige,
            "elements": [self._resume(item) for item in retenus],
            "national_sources": len(nationaux),
            "global_sources": len(elements) - len(nationaux),
            # Servir un élément mondial est permis hors sujets nationaux, mais
            # jamais silencieusement : sa portée est rendue avec lui.
            "note": (
                "Chaque élément porte sa portée. Un élément « global » répond à "
                "une question générale, pas à une question de droit sénégalais."
            ),
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

    @staticmethod
    def _ce_qui_trancherait(sujet, national_exige: bool) -> List[str]:
        """Nomme ce qu'il faudrait ingérer pour que la question trouve réponse."""
        pistes = [
            "Ingérer des documents déclarés `scope: country:sn` sur ce sujet "
            "(`docs/knowledge/README.md`)",
        ]
        if national_exige:
            pistes.append(
                f"Pour « {sujet.value} », la source doit être nationale : Journal "
                "officiel, ministère compétent, ou administration concernée."
            )
        return pistes


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Question à traiter.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(SenegalIntelligenceAgent, input_data)
