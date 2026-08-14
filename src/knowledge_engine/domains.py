"""
Domain coverage: what this platform knows about, measured — and what it does not,
with the reason.

Two lists of empty domains already existed in this repository, both written by
hand inside `scripts/ingest_senegal_domains.py`, both about Senegal only. They
were right when they were written. That is the problem: a hand-written list of
what is missing is a snapshot, and it goes on describing yesterday long after a
domain has been filled or emptied.

This module measures instead. For a subject and a scope it asks three questions
of the repository as it stands, in this order:

1. **Is a source even declared for it?** No registered source means the gap is
   upstream of any acquisition: nothing could be fetched, because nobody has
   said who would be authoritative.
2. **Is one of those sources enabled?** Declared is not enabled (ADR-021).
   A domain whose sources are all disabled is not "failing to acquire" — it has
   never been allowed to try, and those are different states.
3. **Does the base actually hold anything?** Only then is a domain populated.

The distinction matters because the three call for three different actions:
register a source, approve one, or investigate an acquisition that ran and
brought nothing.

**An empty domain is never silent.** `unknown` is not `no`, and an absent domain
must never be indistinguishable from a forgotten one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scope import (
    NATIONAL_SUBJECTS,
    KnowledgeScope,
    KnowledgeSubject,
    normative_split,
    parse_subject,
)
from .source_registry import load_registry


#: Les quatre états d'un domaine. Écrits comme des chaînes plutôt qu'une
#: énumération : ils sortent tels quels dans les rapports, et une énumération
#: n'apporterait ici qu'une conversion de plus.
POPULATED = "POPULATED"
NO_SOURCE = "NO_SOURCE_DECLARED"
NOT_ENABLED = "SOURCES_DECLARED_BUT_DISABLED"
EMPTY = "SOURCES_ENABLED_BUT_EMPTY"

#: Sources actives, et **personne n'a compté**. Cet état a été ajouté parce
#: qu'un test l'a exigé : sans lui, `counter=None` retombait sur `EMPTY`, et le
#: module annonçait « la base est vide » là où il fallait lire « personne n'a
#: regardé ». C'est exactement la confusion que ce fichier prétend empêcher,
#: commise par lui-même.
NOT_MEASURED = "SOURCES_ENABLED_BUT_NOT_MEASURED"

#: Ce qu'il faut faire selon l'état. La distinction est tout l'intérêt du
#: module : trois absences qui se ressemblent appellent trois gestes différents.
ACTIONS = {
    NO_SOURCE: (
        "Inscrire une source au registre : personne n'a encore dit qui ferait "
        "autorité sur ce sujet, donc rien n'a jamais pu être cherché."
    ),
    NOT_ENABLED: (
        "Activer une source déjà inscrite (décision humaine, ADR-021). Inscrire "
        "n'est pas activer, et un domaine dont les sources dorment n'a jamais "
        "eu le droit d'essayer."
    ),
    EMPTY: (
        "Chercher pourquoi l'acquisition n'a rien rapporté : une source active "
        "et une base vide est un échec réel, pas une absence de permission."
    ),
    NOT_MEASURED: (
        "Brancher un compteur : les sources sont actives et personne n'a "
        "regardé ce que la base contient. « Non mesuré » n'est pas « vide »."
    ),
    POPULATED: "Rien : le domaine porte quelque chose.",
}


def _sources_du_sujet(
    sujet: KnowledgeSubject, portee: str, registre: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Les sources déclarées qui couvrent ce sujet pour cette portée.

    Une source mondiale compte pour une portée nationale — sauf pour les sujets
    qui ne se transportent pas (`NATIONAL_SUBJECTS`) : là, une source mondiale
    n'est pas une source de repli, elle est hors sujet.
    """
    national = sujet in NATIONAL_SUBJECTS
    retenues = []
    for source in registre["sources"]:
        if sujet.value not in source["subjects"]:
            continue
        if source["scope"] == portee:
            retenues.append(source)
        elif source["scope"] == "global" and not national:
            retenues.append(source)
    return retenues


def domain_state(
    subject: Any,
    scope: Any = "global",
    counter: Optional[Any] = None,
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    L'état mesuré d'un domaine, et ce qu'il faudrait faire.

    Args:
        subject: Le sujet.
        scope: La portée.
        counter: Fonction `(sujet, portée) -> int` disant combien la base
            contient. Sans elle, le comptage est déclaré non mesuré — et un
            comptage non mesuré ne devient jamais un zéro.
        registre: Le registre déjà chargé.

    Returns:
        L'état, les sources qui le concernent, l'action attendue, et — pour un
        sujet à part normative — ce qu'une source mondiale ne peut pas porter.
    """
    sujet = parse_subject(subject)
    portee = str(KnowledgeScope.parse(scope))
    registre = registre if registre is not None else load_registry()

    sources = _sources_du_sujet(sujet, portee, registre)
    actives = [source for source in sources if source["enabled"]]

    if counter is None:
        elements = None
    else:
        elements = int(counter(sujet.value, portee))

    if elements:
        etat = POPULATED
    elif not sources:
        etat = NO_SOURCE
    elif not actives:
        etat = NOT_ENABLED
    elif elements is None:
        etat = NOT_MEASURED
    else:
        etat = EMPTY

    rapport: Dict[str, Any] = {
        "subject": sujet.value,
        "scope": portee,
        "state": etat,
        "action": ACTIONS[etat],
        "declared_sources": [source["name"] for source in sources],
        "enabled_sources": [source["name"] for source in actives],
        # `None` et non `0` : personne n'a compté, et un comptage absent ne
        # devient pas une base vide.
        "items": elements,
        "national_subject": sujet in NATIONAL_SUBJECTS,
    }

    partage = normative_split(sujet)
    if partage:
        rapport["normative_split"] = partage
        rapport["note"] = (
            "Sujet à part normative : une source mondiale porte l'universel, "
            "jamais ce qu'un territoire prescrit."
        )
    return rapport


def domain_coverage(
    scope: Any = "global",
    counter: Optional[Any] = None,
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    L'état de **tous** les sujets pour une portée.

    Args:
        scope: La portée mesurée.
        counter: Le compteur de la base.
        registre: Le registre déjà chargé.

    Returns:
        Un état par sujet, le décompte par état, et ce que ce rapport ne fait
        pas.
    """
    registre = registre if registre is not None else load_registry()
    etats = [
        domain_state(sujet, scope, counter, registre)
        for sujet in KnowledgeSubject
        if sujet is not KnowledgeSubject.UNSPECIFIED
    ]

    par_etat: Dict[str, int] = {}
    for etat in etats:
        par_etat[etat["state"]] = par_etat.get(etat["state"], 0) + 1

    return {
        "scope": str(KnowledgeScope.parse(scope)),
        "domains": etats,
        "by_state": dict(sorted(par_etat.items())),
        "measured": counter is not None,
        "rules": [
            "Trois absences qui se ressemblent appellent trois gestes "
            "différents : inscrire une source, en activer une, ou chercher "
            "pourquoi une acquisition active n'a rien rapporté.",
            "Inscrire n'est pas activer : un domaine dont les sources dorment "
            "n'a jamais eu le droit d'essayer.",
            "Sans compteur, le nombre d'éléments vaut `null` — jamais zéro — "
            "et l'état dit « non mesuré », jamais « vide ». Un comptage absent "
            "ne devient pas une base vide.",
            "Pour un sujet national, une source mondiale n'est pas un repli : "
            "elle est hors sujet.",
        ],
        "does_not": [
            "Acquérir quoi que ce soit : ce module lit, il ne va rien chercher.",
            "Deviner un domaine à partir d'un autre.",
        ],
    }
