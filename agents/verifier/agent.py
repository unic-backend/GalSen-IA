"""
Fact Verification Agent for GalSen IA (VOLET 36, ch. D).

Chapter C built the measure; this agent is the one that **carries a verdict** and
stops there. Its whole value is in what it refuses to do:

- it **never rewrites the answer**. Correcting a claim would mix the measure and
  the thing measured, and the next reader could no longer tell which is which;
- it **never asks the model whether it was right**. That would measure the
  model's confidence in itself, which is exactly what a verification layer
  exists to escape;
- with **no passage retrieved**, it reports `cannot_verify` — never `supported`.
  A verdict with nothing behind it is worse than no verdict: it looks like a
  check that happened.

`cannot_verify` and `unsupported` are kept apart on purpose. "I found nothing to
compare this to" is not "I compared it and nothing backs it", and a reader acts
differently on each.
"""

from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.factual_evaluation import (
    MESURES_INDISPONIBLES,
    ClaimVerdict,
    assess_claim,
    split_claims,
)

#: Nombre de passages interrogés par affirmation. Assez pour qu'une affirmation
#: trouve son passage, assez peu pour que le verdict reste lisible : un verdict
#: adossé à vingt passages ne se vérifie plus à la main.
PASSAGES_PAR_AFFIRMATION = 5

#: Ce que cet agent ne fera pas, quelle que soit la demande. Énuméré dans la
#: réponse : une limite écrite dans la sortie survit à la lecture, pas celle qui
#: dort dans une docstring.
NON_PRODUIT = (
    "réécriture de la réponse : mesurer et corriger sont deux rôles",
    "avis du modèle sur sa propre réponse : ce serait sa confiance, pas une vérification",
    "verdict « étayé » sans passage : un contrôle qui n'a pas eu lieu",
)


class FactVerificationAgent(BaseAgent):
    """Agent qui confronte des affirmations à des passages, et rapporte."""

    agent_id = "verifier"
    required_engines = ("knowledge",)

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Porte un verdict sur chaque affirmation de la réponse à vérifier.

        Args:
            context: Contexte d'exécution. `options["claims"]` permet de fournir
                les affirmations déjà découpées ; sinon la requête est découpée.

        Returns:
            Un verdict par affirmation, avec le passage qui le porte, et le
            compte de ce qui n'a pas pu être vérifié.
        """
        affirmations = self._affirmations(context)
        if not affirmations:
            return {
                "status": "nothing_to_verify",
                "reason": "Aucune affirmation dans la demande : il n'y a rien à confronter.",
                "claims": [],
                "not_produced": list(NON_PRODUIT),
            }

        verdicts: List[Dict[str, Any]] = []
        passages_vus = 0

        for affirmation in affirmations:
            passages = context.search_knowledge(
                affirmation, limit=PASSAGES_PAR_AFFIRMATION
            )
            passages_vus += len(passages)
            if not passages:
                # Le mode de défaillance nommé au plan : sans passage, on ne dit
                # pas « non étayé » — on dit qu'on n'a pas pu vérifier.
                verdicts.append({
                    "claim": affirmation,
                    "verdict": "cannot_verify",
                    "reason": "Aucun passage retrouvé pour cette affirmation.",
                    "passage": None,
                })
                continue

            evaluation = assess_claim(affirmation, passages)
            verdicts.append(evaluation.to_dict())

        comptes = self._comptes(verdicts)
        return {
            "status": "verified" if passages_vus else "cannot_verify",
            "claims": verdicts,
            "counts": comptes,
            "passages_examined": passages_vus,
            # Ce que la mesure ne sait pas faire voyage avec le verdict : un
            # tableau de « supported » se lit comme un certificat sinon.
            "unavailable": dict(MESURES_INDISPONIBLES),
            "not_produced": list(NON_PRODUIT),
            "note": (
                "Ces verdicts sont lexicaux : « étayé » veut dire que le passage "
                "porte les termes de l'affirmation, pas qu'il l'implique."
            ),
        }

    @staticmethod
    def _affirmations(context: AgentContext) -> List[str]:
        """Retourne les affirmations à vérifier, fournies ou découpées."""
        fournies = context.options.get("claims")
        if fournies:
            return [str(claim).strip() for claim in fournies if str(claim).strip()]
        return split_claims(context.request_text())

    @staticmethod
    def _comptes(verdicts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Compte les verdicts par catégorie, `cannot_verify` compris."""
        categories = [verdict.value for verdict in ClaimVerdict] + ["cannot_verify"]
        comptes = {categorie: 0 for categorie in categories}
        for verdict in verdicts:
            nom = verdict.get("verdict", "cannot_verify")
            comptes[nom] = comptes.get(nom, 0) + 1
        return comptes


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Réponse ou affirmation à vérifier.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(FactVerificationAgent, input_data)
