"""
Following one piece of work across the subsystems it crossed.

Every subsystem here already records what it did. The audit engine keeps events,
the checkpoints keep runs, the routine journal keeps turns, the workflow history
keeps outcomes. What none of them could do until VOLET 66 was answer the
question an operator actually asks at three in the morning: *what happened to
this one job?*

Phase 66.1 gave that job a single identifier that survives the boundaries — a
routine turn's `correlation_id` becomes the workflow's `request_id`, hence the
`request_id` of its audit events. This module reads the identifier back out of
each store and assembles the trail.

It does **not** re-read the audit itself: `src/api/tracing.py` has done that
since VOLET 19, ordering the steps and summing measured durations. Writing a
second reader would give two answers that diverge the day one of them is fixed.
What is new here is the assembly across the subsystems that trace never saw —
the routine turn that started the work, and the checkpoints of the runs it
opened.

Two rules govern the assembly, and both are about honesty rather than
completeness:

- **A store that holds nothing for this identifier says so**, and is
  distinguished from a store that could not be read at all. "No audit event
  carries this identifier" and "the audit engine is unavailable" lead to
  opposite conclusions, and a trail that renders both as an empty list would
  send someone looking in the wrong place.
- **Nothing is inferred from proximity.** Two events a second apart are not the
  same job unless they carry the same identifier. Correlating by timestamp is
  how a trail becomes confidently wrong.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Ce qu'une source peut répondre à propos d'un identifiant.
TROUVE = "FOUND"
RIEN = "NONE"
ILLISIBLE = "UNREADABLE"


def _fragment(state: str, items: Any = None, reason: str = "") -> Dict[str, Any]:
    """Un morceau de piste, avec l'état de la source qui l'a produit."""
    return {"state": state, "items": items if items is not None else [], "reason": reason}


def audit_fragment(
    correlation_id: str, audit_manager: Optional[Any] = None, limit: int = 50
) -> Dict[str, Any]:
    """
    Les événements d'audit portant cet identifiant.

    Args:
        correlation_id: L'identifiant suivi.
        audit_manager: Le gestionnaire d'audit. Celui du registre partagé par
            défaut.
        limit: Nombre maximal d'événements.

    Returns:
        Le fragment, avec l'état de la source.
    """
    # La lecture de l'audit par `request_id` existe depuis le VOLET 19
    # (`src/api/tracing.py`) : elle ordonne les étapes et somme les durées
    # mesurées. La refaire ici en donnerait deux, qui divergeraient le jour où
    # l'une serait corrigée. Ce module ajoute ce qu'elle ne fait pas :
    # rassembler les **autres** sous-systèmes autour du même identifiant.
    from ..api.tracing import build_trace

    gestionnaire = audit_manager
    if gestionnaire is None:
        from ..integration.engine_registry import get_shared_registry

        gestionnaire = get_shared_registry().try_get("audit")

    try:
        trace = build_trace(gestionnaire, correlation_id)
    except Exception as erreur:
        return _fragment(ILLISIBLE, reason=f"{type(erreur).__name__}: {erreur}")

    if not trace.get("available"):
        return _fragment(
            ILLISIBLE, reason=(
                f"{trace.get('reason', 'Audit illisible.')} Cette piste est "
                "incomplète, et l'absence d'événement ne prouve rien."
            ),
        )

    etapes = trace.get("steps") or []
    if not etapes:
        return _fragment(
            RIEN, reason=(
                "Aucun événement d'audit ne porte cet identifiant. Il peut "
                "être exact et son audit déjà purgé."
            ),
        )

    return _fragment(TROUVE, etapes[:limit])


def routine_fragment(
    correlation_id: str, journal: Optional[Any] = None,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Le tour de routine portant cet identifiant, s'il y en a un.

    La lecture passe par le journal, **avec son audience** : suivre une piste ne
    doit pas devenir la façon de lire le journal de quelqu'un d'autre.

    Args:
        correlation_id: L'identifiant suivi.
        journal: Le journal des routines. Sans lui, la source est déclarée
            illisible — pas vide.
        subject: Pour qui la lecture est faite.

    Returns:
        Le fragment, avec l'état de la source.
    """
    if journal is None:
        return _fragment(
            ILLISIBLE, reason=(
                "Aucun journal de routines fourni : impossible de dire si un "
                "tour porte cet identifiant."
            ),
        )

    try:
        tours = journal.find_by_correlation(correlation_id, subject=subject)
    except Exception as erreur:
        return _fragment(ILLISIBLE, reason=f"{type(erreur).__name__}: {erreur}")

    if not tours:
        return _fragment(RIEN, reason="Aucun tour de routine ne porte cet identifiant.")
    return _fragment(TROUVE, tours)


def checkpoint_fragment(
    correlation_id: str, checkpoints: Optional[Any] = None,
    run_ids: Optional[List[str]] = None,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Les points de reprise des exécutions citées par la piste.

    Un point de reprise ne porte pas l'identifiant de corrélation : il porte son
    propre `run_id`, et c'est le tour de routine ou la réponse du routeur qui
    fait le lien. Suivre ce lien plutôt que le deviner est ce qui distingue une
    piste d'une coïncidence.

    Args:
        correlation_id: L'identifiant suivi, pour le message.
        checkpoints: Les points de reprise.
        run_ids: Les exécutions nommées par les autres fragments.
        subject: Pour qui la lecture est faite — un point de reprise appartient
            à qui a lancé l'exécution, et nul autre ne le lit.

    Returns:
        Le fragment, avec l'état de la source.
    """
    if checkpoints is None:
        return _fragment(
            ILLISIBLE, reason="Aucun registre de points de reprise fourni.",
        )
    if not run_ids:
        return _fragment(
            RIEN, reason=(
                f"Aucune exécution n'est nommée par la piste de "
                f"'{correlation_id}' : rien à rapprocher, et rien n'est "
                "rapproché par l'heure."
            ),
        )

    trouves = []
    for identifiant in run_ids:
        try:
            execution = checkpoints.get(identifiant, subject=subject)
        except Exception as erreur:
            return _fragment(ILLISIBLE, reason=f"{type(erreur).__name__}: {erreur}")
        if execution is not None:
            trouves.append(execution.as_dict())

    if not trouves:
        return _fragment(
            RIEN, reason=(
                "Les exécutions nommées n'ont plus de point de reprise : ils "
                "ont pu être élagués."
            ),
        )
    return _fragment(TROUVE, trouves)


def trail(
    correlation_id: str,
    audit_manager: Optional[Any] = None,
    journal: Optional[Any] = None,
    checkpoints: Optional[Any] = None,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Rassemble ce que chaque source sait d'un même travail.

    Args:
        correlation_id: L'identifiant suivi.
        audit_manager: Le gestionnaire d'audit.
        journal: Le journal des routines.
        checkpoints: Les points de reprise.
        subject: Pour qui la piste est lue. Chaque source garde sa propre règle
            d'audience : une piste n'est pas une dérogation.

    Returns:
        La piste, source par source, avec ce qui manque nommé.
    """
    identifiant = (correlation_id or "").strip()
    if not identifiant:
        raise ValueError(
            "Une piste sans identifiant rendrait tout le journal : ce n'est "
            "pas une piste, c'est un export."
        )

    routines = routine_fragment(identifiant, journal, subject=subject)
    audit = audit_fragment(identifiant, audit_manager)

    # Les exécutions viennent des fragments qui les nomment, jamais de l'heure.
    executions = [
        action["run_id"]
        for tour in routines["items"]
        for action in tour.get("actions", [])
        if action.get("run_id")
    ]
    reprises = checkpoint_fragment(
        identifiant, checkpoints, executions, subject=subject,
    )

    fragments = {
        "routine_runs": routines,
        "audit_events": audit,
        "workflow_runs": reprises,
    }
    return {
        "correlation_id": identifiant,
        "fragments": fragments,
        "found_in": [nom for nom, f in fragments.items() if f["state"] == TROUVE],
        "empty_in": [nom for nom, f in fragments.items() if f["state"] == RIEN],
        # Une source illisible est ce qui doit sauter aux yeux : c'est la seule
        # situation où l'absence de trace ne prouve rien.
        "unreadable": [nom for nom, f in fragments.items() if f["state"] == ILLISIBLE],
        "rules": [
            "Une source vide et une source illisible ne sont pas la même "
            "chose : « aucun événement ne porte cet identifiant » et « le "
            "moteur d'audit est indisponible » mènent à des conclusions "
            "opposées.",
            "Rien n'est rapproché par l'heure : deux événements à une seconde "
            "d'intervalle ne sont pas le même travail sans le même "
            "identifiant.",
            "L'identifiant traverse les frontières : le tour de routine, le "
            "workflow qu'il déclenche et les événements d'audit de celui-ci "
            "portent le même.",
        ],
    }


def observability_report() -> Dict[str, Any]:
    """
    Ce qui est traçable de bout en bout, et ce qui ne l'est pas.

    Returns:
        Les sources reliées par l'identifiant, et les limites assumées.
    """
    return {
        "correlated": {
            "routine_runs": "Le tour porte l'identifiant, dès avant ses gardes.",
            "workflow_runs": (
                "L'exécution déclenchée reprend l'identifiant du tour au lieu "
                "d'en générer un."
            ),
            "audit_events": (
                "Les événements du routeur portent ce `request_id`, donc celui "
                "du tour."
            ),
        },
        "not_correlated": {
            "notifications": (
                "Un événement de plateforme ne porte pas encore "
                "l'identifiant : il nomme la routine ou l'exécution, ce qui "
                "suffit à la retrouver mais pas à la relier automatiquement."
            ),
            "tool_calls": (
                "Un appel d'outil dans une routine n'ouvre pas d'exécution : il "
                "n'y a rien à relier au-delà du tour lui-même."
            ),
        },
        "does_not": [
            "Corréler par l'heure : c'est ainsi qu'une piste devient "
            "confiante et fausse.",
            "Reconstituer une piste effacée : un point de reprise élagué est "
            "dit élagué, pas deviné.",
        ],
    }
