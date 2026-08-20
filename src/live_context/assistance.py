"""
Ce qu'il y a à dire pendant une session, et surtout ce qu'il n'y a pas à dire
(L08, ADR-033, §19 et §20 de la directive Live Context).

## Le `NudgeEngine` du §20 existe déjà, et il s'appelle `src/proactive/`

L02 l'a mesuré avant que la moindre ligne soit écrite ici. `src/proactive/`
porte les trois pièces que §20 demande : une observation qui **transporte ses
preuves**, une suppression des répétitions, et l'interdiction d'agir.

Sa suppression des répétitions est même plus précise que celle de Call.md. Un
délai de deux minutes fait revenir une suggestion parce que le temps a passé ;
une **empreinte des preuves** la fait revenir parce que la situation a changé.
Écarter « 3 fichiers sans test » ne masque pas « 300 fichiers sans test » six
mois plus tard.

Ce module n'écrit donc **aucun moteur de suggestion, aucun journal et aucun
minuteur**. Il écrit des détecteurs qui lisent un `LiveContextState` et rendent
des `proactive.Observation`.

## La règle qui décide de tout : une suggestion ne repose jamais sur un inconnu

C'est là que ce module gagne ou perd son droit d'exister. Suggérer « passe en
wolof » quand la langue est `UNKNOWN`, ou « Awa devrait répondre » quand aucun
locuteur n'est identifié, produirait exactement la fabrication que tout le
programme refuse — en plus convaincant, parce qu'une suggestion se lit comme un
conseil et non comme une donnée.

Les détecteurs ne lisent donc que des observations `is_known`. Sur cette
machine, où presque rien n'est mesurable, ils sont **presque toujours muets**,
et c'est le résultat correct : `src/proactive/` dit déjà qu'un détecteur qui ne
trouve rien rend une liste vide, et que c'est le cas normal.

## Une seule chose reste dicible quand rien n'est mesuré

« Rien n'a été mesuré, voici pourquoi, voici ce qu'il faudrait installer. »
C'est une suggestion adressée à l'opérateur, pas au participant, et elle porte
ses preuves : les comptes de l'état et les constats d'absence.

## Rien n'agit, et rien n'est dit à la place de quelqu'un

Une observation propose et nomme qui décide (`decided_by`). Aucune ne parle
dans la session, n'écrit en mémoire ni ne déclenche d'outil : la mémoire est
gouvernée par la permission et le consentement (volet ultérieur), et l'exécution
d'outil par le portillon d'ADR-006.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.proactive.journal import SuggestionJournal
from src.proactive.observations import Observation as Suggestion
from src.proactive.observations import observation, sort_observations

from .state import ABSENT, INCONNU, LiveContextState

#: Les détecteurs live, dans l'ordre où ils sont exécutés.
DETECTEURS_LIVE = (
    "context_conflict",
    "missing_capability",
    "nothing_measured",
)


def conflits_de_contexte(state: LiveContextState) -> List[Suggestion]:
    """
    Signale les désaccords que la fusion a enregistrés sans les résoudre.

    Args:
        state: L'état de la session.

    Returns:
        Une suggestion par sujet en conflit. C'est le cas où une suggestion est
        pleinement justifiée : la fusion refuse d'arbitrer **précisément pour
        qu'un humain le fasse**, et ne rien dire reviendrait à enterrer le
        désaccord au lieu de le rendre.
    """
    trouvees: List[Suggestion] = []
    for conflit in state.conflicts():
        trouvees.append(observation(
            source="live_context.context_conflict",
            finding=(f"Deux observations de « {conflit['subject']} » ne "
                     f"concordent pas : {', '.join(conflit['values'])}."),
            evidence={
                "subject": conflit["subject"],
                "values": conflit["values"],
                "providers": conflit["providers"],
                "observations": conflit["observations"],
                "session_id": state.session_id,
            },
            suggested_action=("Trancher le désaccord, ou déclarer lequel des "
                              "fournisseurs fait foi pour ce sujet. La fusion "
                              "n'arbitre pas."),
            decided_by="operator",
            priority="worth_doing",
        ))
    return trouvees


def capacites_manquantes(state: LiveContextState) -> List[Suggestion]:
    """
    Signale ce qui est absent et qu'un opérateur pourrait installer.

    Args:
        state: L'état de la session.

    Returns:
        Une suggestion par sujet `ABSENT`. Une absence porte toujours son
        constat — `state.absent()` le refuse sinon — donc la preuve existe
        forcément, et l'opérateur lit **quoi** manque plutôt que « le contexte
        live est indisponible ».

    Note:
        Les `UNKNOWN` sont volontairement ignorés. Une inconnue n'appelle aucune
        installation : elle attend une mesure, et suggérer d'agir dessus
        transformerait « personne ne sait » en « il manque quelque chose ».
    """
    trouvees: List[Suggestion] = []
    vus: set = set()
    for element in state.observations:
        if element.status != ABSENT or element.subject in vus:
            continue
        vus.add(element.subject)
        trouvees.append(observation(
            source="live_context.missing_capability",
            finding=f"« {element.subject} » est absent : {element.detail}",
            evidence={
                "subject": element.subject,
                "modality": element.modality,
                "detail": element.detail,
                "session_id": state.session_id,
            },
            suggested_action=("Installer ou brancher ce que le constat nomme, "
                              "ou accepter que ce sujet reste hors de portée."),
            decided_by="operator",
            priority="for_information",
        ))
    return trouvees


def rien_de_mesure(state: LiveContextState) -> List[Suggestion]:
    """
    Dit qu'aucune assistance n'est possible, quand c'est le cas.

    Args:
        state: L'état de la session.

    Returns:
        Une suggestion, et une seule, quand l'état ne contient **aucune**
        observation connue. Rien sinon.

    Note:
        C'est la seule chose qui reste dicible quand rien n'est mesuré, et elle
        vaut mieux que le silence : le silence se lit comme « tout va bien ».
        Un état vide n'en produit pas non plus — une session qui n'a pas
        commencé n'a rien à signaler.
    """
    if not state.observations:
        return []
    connues = [o for o in state.observations if o.is_known]
    if connues:
        return []
    comptes = state.counts()
    return [observation(
        source="live_context.nothing_measured",
        finding=("Aucune observation connue dans cette session : rien ne peut "
                 "être suggéré à partir du contenu."),
        evidence={
            "session_id": state.session_id,
            "observations": len(state.observations),
            "unknown": comptes[INCONNU],
            "absent": comptes[ABSENT],
            "absent_subjects": sorted({o.subject for o in state.observations
                                       if o.status == ABSENT}),
        },
        suggested_action=("Lire les constats d'absence pour savoir quoi "
                          "installer. Aucune assistance de contenu n'est "
                          "possible tant que rien n'est mesuré."),
        decided_by="operator",
        priority="blocking",
    )]


#: Les détecteurs, par nom. Un nom absent d'ici n'est pas exécutable : la table
#: est la déclaration, la fonction n'en est que la réalisation.
_FONCTIONS = {
    "context_conflict": conflits_de_contexte,
    "missing_capability": capacites_manquantes,
    "nothing_measured": rien_de_mesure,
}


class AssistanceRefused(ValueError):
    """Une assistance impossible telle quelle."""


def run_live_detector(nom: str, state: LiveContextState) -> Dict[str, Any]:
    """
    Exécute un détecteur live et rend son résultat, panne comprise.

    Args:
        nom: Un nom de `DETECTEURS_LIVE`.
        state: L'état de la session.

    Returns:
        `status` valant `ok` ou `failed`, et les suggestions trouvées. **Un
        détecteur muet et un détecteur cassé ne se confondent pas** : c'est la
        distinction que `proactive/scan.py` tient déjà, reprise ici.

    Raises:
        AssistanceRefused: Si le détecteur n'est pas déclaré.
    """
    if nom not in _FONCTIONS:
        raise AssistanceRefused(
            f"Détecteur « {nom} » non déclaré. Déclarés : {list(DETECTEURS_LIVE)}."
        )
    try:
        return {"detector": nom, "status": "ok",
                "observations": _FONCTIONS[nom](state), "reason": ""}
    except Exception as erreur:  # noqa: BLE001 — la panne est rapportée, pas cachée
        return {"detector": nom, "status": "failed", "observations": [],
                "reason": f"{type(erreur).__name__}: {erreur}"}


def live_scan(state: LiveContextState,
              journal: Optional[SuggestionJournal] = None,
              detectors: Optional[List[str]] = None,
              record: bool = True) -> Dict[str, Any]:
    """
    Passe les détecteurs live sur un état, et rend ce qui mérite d'être dit.

    Args:
        state: L'état de la session.
        journal: Le journal des suggestions ; celui du répertoire de données
            sinon. **C'est celui de `src/proactive/`** — il n'y en a pas un
            second pour le live, sans quoi écarter une suggestion à un endroit
            la laisserait revenir de l'autre.
        detectors: Les détecteurs à exécuter ; tous par défaut.
        record: Inscrire au journal ce qui a été montré.

    Returns:
        Les suggestions retenues, le nombre de suggestions tues, les détecteurs
        en panne, et `acted: False`.

    Note:
        Une suggestion écartée revient quand ses preuves changent, jamais quand
        le temps passe. Un minuteur de deux minutes ferait revenir une
        suggestion sur une situation identique ; ici il faut que la situation
        ait bougé.
    """
    carnet = journal if journal is not None else SuggestionJournal()
    noms = detectors if detectors is not None else list(DETECTEURS_LIVE)

    trouvees: List[Suggestion] = []
    en_panne: List[Dict[str, str]] = []
    for nom in noms:
        resultat = run_live_detector(nom, state)
        if resultat["status"] == "failed":
            en_panne.append({"detector": nom, "reason": resultat["reason"]})
            continue
        trouvees.extend(resultat["observations"])

    retenues = sort_observations(carnet.filter(trouvees))
    if record and retenues:
        carnet.record_surfaced(retenues)

    return {
        "session_id": state.session_id,
        "observations": [s.to_dict() for s in retenues],
        "count": len(retenues),
        "silenced": len(trouvees) - len(retenues),
        "detectors_run": len(noms),
        "detectors_failed": en_panne,
        "acted": False,
        "spoke_in_session": False,
        "note": ("Aucune action n'a été exécutée et rien n'a été dit dans la "
                 "session. Chaque suggestion nomme qui doit décider."),
    }


def assistance_report() -> Dict[str, Any]:
    """
    Ce que la couche d'assistance garantit, et ce qu'elle ne construit pas.

    Returns:
        Les détecteurs déclarés, ce qui est réutilisé, et les règles tenues.
    """
    return {
        "detectors": list(DETECTEURS_LIVE),
        "builds_nudge_engine": False,
        "builds_journal": False,
        "uses_cooldown_timer": False,
        "reused": [
            "proactive/observations.py — une suggestion porte ses preuves et "
            "nomme qui décide",
            "proactive/journal.py — la répétition est supprimée par empreinte "
            "des preuves",
            "proactive/scan.py — un détecteur muet et un détecteur cassé ne se "
            "confondent pas",
        ],
        "rules": [
            "Une suggestion ne repose jamais sur un UNKNOWN : conseiller à "
            "partir d'une inconnue est plus convaincant qu'une donnée fausse, "
            "donc pire.",
            "Un ABSENT est adressé à l'opérateur ; un UNKNOWN n'appelle aucune "
            "installation.",
            "Aucun moteur de suggestion, aucun journal et aucun minuteur ne "
            "sont écrits ici : §20 décrit `src/proactive/`.",
            "Une suggestion revient quand ses preuves changent, jamais quand "
            "le temps passe.",
            "Rien n'agit, rien n'est dit dans la session, rien n'est écrit en "
            "mémoire.",
            "Un détecteur qui ne trouve rien rend une liste vide, et c'est le "
            "cas normal.",
        ],
    }
