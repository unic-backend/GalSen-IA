"""
Trace de la seule décision que la plateforme prend (VOLET 22, chapitre 03).

Le manuel décrit un moteur de décision à onze composants et quatorze étapes.
Aucun n'existe, et ce module n'en fabrique aucun. Il rend visible une chose
mesurée : la plateforme **prend** bien une décision — `PlannerAgent` détecte les
intentions d'une demande et en déduit les agents nécessaires — et cette décision
est **jetée**.

Mesuré le 2026-08-11, sur « surveille les logs de production » :

```
agents recommandés par le planificateur : researcher, deployment, monitor
agents réellement exécutés              : 9 (le pipeline déclaré, en entier)
```

Le chapitre 03 range l'enregistrement de la décision à l'étape 10 et
l'évaluation de l'explicabilité parmi ses contrôles qualité. Une décision prise
puis perdue n'est ni enregistrée ni explicable : personne ne peut dire qu'elle a
eu lieu, encore moins pourquoi elle n'a rien changé.

Ce module ne change pas l'exécution. Faire suivre la recommandation est un choix
de conception sur le pipeline — inscrit au backlog, comme l'agent `tester` du
VOLET 19 — et non le travail d'une phase de mesure.
"""

from typing import Any, Dict, Iterable, List, Optional

# Le routeur est l'orchestrateur : il ne figure dans aucune recommandation et
# ne s'exécute pas comme un agent.
ORCHESTRATEUR = "router"


def _recommandation(resultats: Iterable[Dict[str, Any]]) -> Optional[List[str]]:
    """
    Extrait les agents recommandés par le planificateur.

    Args:
        resultats: les résultats d'agents d'une exécution.

    Returns:
        La liste recommandée, ou None si le planificateur n'a pas tourné — cas
        distinct d'une recommandation vide, qui serait une décision de ne rien
        mobiliser.
    """
    for resultat in resultats:
        if resultat.get("agent") != "planner":
            continue
        sortie = resultat.get("result") or {}
        recommandes = sortie.get("agents_required")
        if isinstance(recommandes, (list, tuple)):
            return [str(agent) for agent in recommandes]
    return None


def recommended_agents(agent_results: Iterable[Dict[str, Any]]) -> Optional[List[str]]:
    """
    Retourne les agents recommandés par le planificateur, ou None.

    Exposée pour que l'orchestrateur puisse **suivre** la recommandation quand
    le workflow le déclare (`execution.agent_selection: planner`). C'est le
    branchement que le VOLET 22 avait mesuré sans le faire : la décision était
    calculée puis jetée.

    None signifie « le planificateur n'a pas tourné », ce qui n'est pas une
    liste vide : décider de ne mobiliser personne est une décision, ne pas
    décider n'en est pas une.
    """
    return _recommandation(agent_results)


def selection_appliquee(pipeline: Iterable[str],
                        recommandes: Optional[Iterable[str]]) -> Optional[List[str]]:
    """
    Restreint un pipeline aux agents recommandés, sans jamais l'élargir.

    Le workflow déclaré reste l'autorité sur ce qui **peut** tourner ; le
    planificateur décide seulement ce qui tourne **parmi cela**. Un
    planificateur qui pourrait ajouter un agent absent de `workflows.yaml`
    contournerait la déclaration, et donc la revue humaine qui l'accompagne.

    Args:
        pipeline: les agents déclarés, dans l'ordre.
        recommandes: la recommandation du planificateur, ou None.

    **Trois cas, pas deux.** `recommended_agents()` distingue déjà « le
    planificateur n'a pas tourné » de « il n'a mobilisé personne » — sa
    docstring le dit : *décider de ne mobiliser personne est une décision, ne
    pas décider n'en est pas une*. Cette fonction écrasait la distinction une
    ligne plus bas, avec `restreint or None`, si bien qu'un plan délibérément
    vide relançait le pipeline entier.

    Mesuré le 2026-08-23 : l'intention `conversation` du planificateur ne
    mobilise aucun agent, et « bonjour » traversait quand même le `researcher`
    pendant 1 092 ms.

    Args:
        pipeline: les agents déclarés, dans l'ordre.
        recommandes: la recommandation du planificateur, ou None.

    Returns:
        - `None` — la recommandation est **inutilisable** : planificateur
          absent, ou agents nommés dont aucun n'est déclaré dans le workflow.
          L'appelant garde le pipeline entier : ne rien exécuter parce qu'une
          heuristique n'a rien reconnu serait pire que d'en faire trop.
        - `[]` — le planificateur a **décidé** de ne mobiliser personne.
          L'appelant n'exécute personne, et c'est le plan.
        - une liste — le pipeline restreint.
    """
    if recommandes is None:
        return None
    retenus = set(recommandes)
    if not retenus:
        # Une décision, pas une absence de décision.
        return []
    restreint = [agent for agent in pipeline if agent in retenus]
    return restreint or None


def decision_trace(agent_results: Iterable[Dict[str, Any]],
                   executed_agents: Iterable[str],
                   applied: bool = False) -> Dict[str, Any]:
    """
    Compare ce que le planificateur a décidé et ce qui a réellement tourné.

    Args:
        agent_results: les résultats produits par les agents de l'exécution.
        executed_agents: les identifiants des agents effectivement exécutés.

    Returns:
        La recommandation, l'exécution, l'écart entre les deux, et le fait que
        la recommandation **n'est pas appliquée**. Ce dernier point est explicite
        et non déductible : sans lui, un lecteur croirait que la décision oriente
        l'exécution.
    """
    resultats = list(agent_results)
    executes = [agent for agent in executed_agents if agent != ORCHESTRATEUR]
    recommandes = _recommandation(resultats)

    if recommandes is None:
        return {
            "recommended_agents": None,
            "executed_agents": executes,
            "applied": False,
            "detail": (
                "Le planificateur n'a pas tourné : aucune décision n'a été prise "
                "sur les agents à mobiliser."
            ),
        }

    ensemble_recommande = set(recommandes)
    ensemble_execute = set(executes)

    return {
        "recommended_agents": recommandes,
        "executed_agents": executes,
        # Exécutés sans avoir été recommandés : le coût que la décision aurait
        # évité si elle était suivie.
        "executed_not_recommended": sorted(ensemble_execute - ensemble_recommande),
        # Recommandés et absents de l'exécution : le manque, symétrique du coût.
        "recommended_not_executed": sorted(ensemble_recommande - ensemble_execute),
        "applied": applied,
        "detail": (
            "La recommandation du planificateur a restreint le pipeline déclaré "
            "(execution.agent_selection: planner)."
            if applied else
            "Le pipeline est déclaré dans workflows.yaml et exécuté tel quel ; "
            "la recommandation du planificateur est enregistrée, jamais suivie."
        ),
    }
