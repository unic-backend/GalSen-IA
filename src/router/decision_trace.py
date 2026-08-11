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


def decision_trace(agent_results: Iterable[Dict[str, Any]],
                   executed_agents: Iterable[str]) -> Dict[str, Any]:
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
        "applied": False,
        "detail": (
            "Le pipeline est déclaré dans workflows.yaml et exécuté tel quel ; "
            "la recommandation du planificateur est enregistrée, jamais suivie."
        ),
    }
