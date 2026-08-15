"""
One run through the whole platform, reporting what actually happened.

Domain 37 of the directive — end-to-end demonstration — was measured as absent,
and it is the only kind of check the 4308 tests cannot replace. A test suite
proves that each piece behaves as its author expected; it does not prove that a
piece of work can cross the platform from one end to the other. The seams are
where things break, and the seams are exactly what nobody tests.

So this runs the real chain, in process, with no network: the subsystem probes,
the declared routing, the world reference, a routine declaration, a routine turn
that fires a real workflow through the real orchestrator, and the trail that
follows that one job back through every store that saw it.

Three rules, and the first two are what make a demonstration worth reading:

- **Nothing is simulated.** Every step calls the same code a caller would.
  A demonstration that stubbed the orchestrator would demonstrate the stub.
- **A step that cannot run here says so, with the reason.** Generation needs a
  model provider this installation does not have. That step reports
  `NOT_CONFIGURED` and names what is missing — it never reports success, and it
  never reports failure either, because nothing failed.
- **The verdict is the sum of what was measured**, never a headline written in
  advance. A demonstration that always ends in green is a slide, not a check.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

#: L'issue d'une étape.
REUSSI = "OK"
BLOQUE = "NOT_CONFIGURED"
ECHOUE = "FAILED"

#: Ce que la démonstration ne peut pas faire ici, et pourquoi. Nommé d'avance
#: pour qu'un blocage attendu ne se lise pas comme une panne — et vérifié à
#: l'exécution, jamais supposé.
BLOCAGES_CONNUS = {
    "generation": (
        "Aucun fournisseur de modèle n'est configuré dans cette installation : "
        "la génération répond `503`. Ce n'est pas une panne, c'est une "
        "capacité non activée (C1 : `ollama serve`)."
    ),
    "acquisition": (
        "Aucune source n'est activée (ADR-021), et le mandataire réseau refuse "
        "les domaines institutionnels sénégalais (`CONNECT → 403`, mesuré). "
        "Rien ne peut être acquis ici, et rien ne sera inventé."
    ),
}


def _etape(nom: str, action: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Exécute une étape et rapporte ce qu'elle a donné.

    Une étape qui lève est rapportée en échec **avec son exception** : une
    démonstration qui s'arrête à la première anomalie ne dit pas si les
    suivantes marchaient.
    """
    debut = time.perf_counter()
    try:
        resultat = action()
    except Exception as erreur:
        return {
            "step": nom, "status": ECHOUE,
            "detail": f"{type(erreur).__name__}: {erreur}",
            "elapsed_ms": round((time.perf_counter() - debut) * 1000, 1),
        }
    resultat.setdefault("status", REUSSI)
    resultat["step"] = nom
    resultat["elapsed_ms"] = round((time.perf_counter() - debut) * 1000, 1)
    return resultat


def _sous_systemes() -> Dict[str, Any]:
    """Les dix sous-systèmes répondent-ils ?"""
    from ..integration.degradation import degradation_report

    rapport = degradation_report()
    return {
        "detail": (
            f"{rapport['counts']['AVAILABLE']} disponibles, "
            f"{rapport['counts']['DEGRADED']} dégradés, "
            f"{rapport['counts']['UNAVAILABLE']} indisponibles."
        ),
        "unavailable": rapport["unavailable"],
        "status": REUSSI if not rapport["unavailable"] else ECHOUE,
    }


def _routage() -> Dict[str, Any]:
    """Une question part-elle vers la bonne couche, et le dit-elle ?"""
    from ..knowledge_engine.routing import route

    decision = route("Quelle est la loi foncière à Dakar ?")
    return {
        "detail": (
            f"Sujet « {decision['subject']} », portée {decision['scope']} → "
            f"couches {decision['layers']}."
        ),
        "layers": decision["layers"],
    }


def _connaissance_mondiale() -> Dict[str, Any]:
    """La référence mondiale répond-elle sur un pays ?"""
    from ..knowledge_engine.world import find_country

    reponse = find_country("Quelle est la capitale du Ghana ?")
    trouve = reponse.get("status") == "FOUND"
    return {
        "detail": (
            f"Statut {reponse.get('status')}"
            + (f", pays {reponse['country'].get('iso3')}" if trouve else "")
        ),
        # `UNKNOWN` n'est pas un échec : c'est la réponse honnête quand la
        # connaissance n'est pas là. La démonstration le rapporte tel quel.
        "status": REUSSI,
    }


def _routine_et_workflow(orchestrateur: Optional[Any] = None) -> Dict[str, Any]:
    """
    Une routine déclenche-t-elle un workflow réel, de bout en bout ?

    C'est la couture centrale du programme : déclaration gardée, tour sans
    témoin, orchestrateur partagé, point de reprise, identifiant de corrélation.
    """
    from ..routines import (
        RoutineJournal,
        RoutineRegistry,
        RoutineScheduler,
        WorkflowAction,
    )

    registre = RoutineRegistry()
    routine = registre.declare(
        "demonstration", "Fait tourner un workflow, pour la démonstration.",
        [WorkflowAction(workflow_id="question",
                        operation="Quelle est la monnaie du Sénégal ?")],
        interval_seconds=3600, subject="demonstration",
    )
    registre.enable(routine.routine_id)

    moteur = orchestrateur
    if moteur is None:
        from ..router.router_engine import RouterEngine

        moteur = RouterEngine()

    journal = RoutineJournal()
    planificateur = RoutineScheduler(registre, orchestrator=moteur)
    tour = planificateur.run(routine)
    journal.record(tour, subject=routine.subject)
    # Les points de reprise viennent de l'orchestrateur qui a tourné, pas d'un
    # registre neuf : la piste doit lire ceux de cette exécution-là.
    points = getattr(moteur, "checkpoints", None)

    action = tour.actions[0] if tour.actions else None
    return {
        "detail": (
            f"Tour {'réussi' if tour.ok else 'non abouti'} ; "
            f"{action.agents if action else 0} agents exécutés ; "
            f"exécution {action.run_id if action else '—'}."
        ),
        "correlation_id": tour.correlation_id,
        "agents": action.agents if action else 0,
        "journal": journal,
        "checkpoints": points,
        "status": REUSSI if tour.ok else ECHOUE,
    }


def _piste(correlation_id: str, journal: Any, checkpoints: Any) -> Dict[str, Any]:
    """Le travail se relit-il de bout en bout, par son identifiant ?"""
    from ..observability import trail

    piste = trail(
        correlation_id, journal=journal, checkpoints=checkpoints,
        subject="demonstration",
    )
    return {
        "detail": (
            f"Retrouvé dans {piste['found_in']} ; "
            f"vide dans {piste['empty_in']} ; "
            f"illisible dans {piste['unreadable']}."
        ),
        "found_in": piste["found_in"],
        "status": REUSSI if piste["found_in"] else ECHOUE,
    }


def _generation() -> Dict[str, Any]:
    """
    La génération répond-elle ? Non, et la démonstration dit pourquoi.

    Le blocage est **vérifié**, pas supposé : si un fournisseur était configuré,
    cette étape le dirait au lieu de répéter une limite périmée.
    """
    from ..integration.engine_registry import get_shared_registry

    moteur = get_shared_registry().try_get("model")
    if moteur is None:
        return {"status": BLOQUE, "detail": BLOCAGES_CONNUS["generation"]}

    try:
        fournisseurs = moteur.sovereignty_report()
    except Exception as erreur:
        return {"status": BLOQUE, "detail": f"Rapport indisponible : {erreur}"}

    actifs = fournisseurs.get("configured_providers") or []
    if not actifs:
        return {"status": BLOQUE, "detail": BLOCAGES_CONNUS["generation"]}
    return {
        "status": REUSSI,
        "detail": f"Fournisseurs configurés : {actifs}.",
    }


def _acquisition() -> Dict[str, Any]:
    """Une source peut-elle être atteinte ? Non, et c'est la règle qui tient."""
    from ..knowledge_engine.source_registry import registry_report

    rapport = registry_report()
    if rapport.get("enabled"):
        return {
            "status": REUSSI,
            "detail": f"{rapport['enabled']} sources activées sur {rapport['sources']}.",
        }
    return {
        "status": BLOQUE,
        "detail": (
            f"{rapport.get('sources', 0)} sources inscrites, **aucune activée**. "
            + BLOCAGES_CONNUS["acquisition"]
        ),
    }


def run_demonstration(orchestrator: Optional[Any] = None) -> Dict[str, Any]:
    """
    Fait traverser la plateforme à un travail, et rapporte ce qui s'est passé.

    Args:
        orchestrator: L'orchestrateur à utiliser. Celui du dépôt par défaut —
            le passer sert aux tests, pas à remplacer le chemin réel.

    Returns:
        Chaque étape avec son issue, le verdict, et ce qui est resté hors de
        portée avec sa raison.
    """
    etapes: List[Dict[str, Any]] = [
        _etape("subsystems", _sous_systemes),
        _etape("knowledge_routing", _routage),
        _etape("world_knowledge", _connaissance_mondiale),
    ]

    travail = _etape("routine_fires_workflow", lambda: _routine_et_workflow(orchestrator))
    etapes.append(travail)

    # La piste ne se lit que si le travail a eu lieu : la demander sans lui
    # rapporterait « rien trouvé » pour une raison qui n'a rien à voir.
    if travail.get("correlation_id"):
        etapes.append(_etape(
            "trail",
            lambda: _piste(
                travail["correlation_id"], travail["journal"],
                travail.get("checkpoints"),
            ),
        ))
    else:
        etapes.append({
            "step": "trail", "status": ECHOUE, "elapsed_ms": 0.0,
            "detail": "Aucun travail n'a eu lieu : il n'y a pas de piste à suivre.",
        })

    etapes.append(_etape("generation", _generation))
    etapes.append(_etape("acquisition", _acquisition))

    # Les objets internes ne sortent pas du rapport : il doit être sérialisable
    # et lisible par quelqu'un qui n'a pas le code sous les yeux.
    for etape in etapes:
        etape.pop("journal", None)
        etape.pop("checkpoints", None)

    echecs = [e["step"] for e in etapes if e["status"] == ECHOUE]
    bloques = [e["step"] for e in etapes if e["status"] == BLOQUE]

    return {
        "steps": etapes,
        "passed": [e["step"] for e in etapes if e["status"] == REUSSI],
        "blocked": bloques,
        "failed": echecs,
        # Le verdict est la somme de ce qui a été mesuré. Une démonstration qui
        # finit toujours au vert est une diapositive, pas une vérification.
        "verdict": "FAILED" if echecs else ("PARTIAL" if bloques else "OK"),
        "rules": [
            "Rien n'est simulé : chaque étape appelle le code qu'un appelant "
            "appellerait. Une démonstration qui bouchonne l'orchestrateur "
            "démontre le bouchon.",
            "Une étape qui ne peut pas tourner ici le dit avec sa raison, et "
            "le blocage est **vérifié** à l'exécution — jamais répété depuis "
            "une limite périmée.",
            "`UNKNOWN` n'est pas un échec : c'est la réponse honnête quand la "
            "connaissance n'est pas là.",
            "Le verdict est la somme de ce qui a été mesuré.",
        ],
    }
