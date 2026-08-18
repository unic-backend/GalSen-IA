"""
Ce que la base ne couvre pas, **mesuré** (VOLET 35, chapitre 06).

Un manque est un couple `sujet × portée` que de **vraies questions** ont touché
et que la base n'a pas su servir. La nuance porte tout le chapitre :

> Un manque que personne n'a jamais demandé n'est pas un manque, c'est une
> supposition sur l'avenir.

Rien n'empêche d'écrire « il nous manque du droit du travail » — mais tant que
personne ne l'a demandé, cette phrase classe une priorité sur une intuition. Ce
module ne lit donc qu'une chose : les recherches réellement passées par la
plateforme, telles que l'audit les a consignées.

## D'où vient le signal

`AgentContext.search_knowledge()` consigne chaque recherche dans l'audit
(`AuditEventType.KNOWLEDGE`, action `search_knowledge`), avec la requête et le
nombre de résultats. Ce journal existait pour la traçabilité ; il sert ici de
mesure d'usage — aucun second journal n'est créé.

## Ce que le module ne fait pas

Il ne propose aucune source : c'est le chapitre 07, et il ne propose que depuis
le registre. Il ne collecte rien. Il ne déduit pas non plus un manque d'une
seule question — une recherche unique et malheureuse arrive, et bâtir une
priorité dessus reviendrait à confondre un accident avec un besoin.
"""

from typing import Any, Dict, List, Optional

from .markers import sujets_reperes
from .scope import KnowledgeSubject
from .scoped_retrieval import detect_scope

#: Nombre de questions distinctes avant de parler de manque. Une recherche
#: unique sans résultat est un accident ; deux disent un usage.
SEUIL_DE_MANQUE = 2

#: Nombre d'événements d'audit lus. Assez pour voir un usage, assez peu pour que
#: la mesure reste instantanée.
EVENEMENTS_LUS = 500


def _evenements(audit: Any = None, limit: int = EVENEMENTS_LUS) -> List[Any]:
    """Retourne les recherches de connaissance consignées, ou une liste vide."""
    moteur = audit
    if moteur is None:
        try:
            from src.integration.engine_registry import get_shared_registry

            moteur = get_shared_registry().try_get("audit")
        except Exception:
            return []
    if moteur is None:
        return []
    try:
        return list(moteur.list_events(limit=limit, action="search_knowledge"))
    except Exception:
        # Un audit illisible rend « aucune question connue », pas « aucun
        # manque » : la distinction est portée par `measured` du rapport.
        return []


def _question_de(evenement: Any) -> str:
    """Retourne la requête consignée dans un événement d'audit."""
    metadonnees = getattr(evenement, "metadata", None) or {}
    return str(metadonnees.get("query") or getattr(evenement, "user_request", "") or "")


def _resultats_de(evenement: Any) -> int:
    """Retourne le nombre de résultats rendus par cette recherche."""
    metadonnees = getattr(evenement, "metadata", None) or {}
    try:
        return int(metadonnees.get("results_count", 0))
    except (TypeError, ValueError):
        return 0


def detect_gaps(
    audit: Any = None,
    limit: int = EVENEMENTS_LUS,
    threshold: int = SEUIL_DE_MANQUE,
) -> Dict[str, Any]:
    """
    Mesure les couples `sujet × portée` que la base n'a pas su servir.

    Args:
        audit: Moteur d'audit ; celui du registre partagé par défaut.
        limit: Nombre d'événements lus.
        threshold: Questions sans résultat à partir desquelles on parle de manque.

    Returns:
        Les manques mesurés, les couples couverts, et le nombre de questions
        réellement lues. `measured: 0` dit « aucune question connue » — ce
        n'est **pas** « aucun manque », et le rapport garde les deux distincts.
    """
    evenements = _evenements(audit, limit)

    couples: Dict[str, Dict[str, Any]] = {}
    for evenement in evenements:
        question = _question_de(evenement).strip()
        if not question:
            continue
        sujets = sujets_reperes(question) or [KnowledgeSubject.UNSPECIFIED.value]
        portee = detect_scope(question)["scope"]
        for sujet in sujets:
            cle = f"{sujet}|{portee}"
            entree = couples.setdefault(cle, {
                "subject": sujet,
                "scope": portee,
                "questions": 0,
                "unanswered": 0,
                "examples": [],
            })
            entree["questions"] += 1
            if _resultats_de(evenement) == 0:
                entree["unanswered"] += 1
                if question not in entree["examples"] and len(entree["examples"]) < 3:
                    # Les exemples sont des questions réelles : un manque
                    # illustré par une question inventée serait invérifiable.
                    entree["examples"].append(question[:200])

    manques = sorted(
        (entree for entree in couples.values() if entree["unanswered"] >= threshold),
        key=lambda entree: (-entree["unanswered"], entree["subject"]),
    )
    couverts = [
        {"subject": entree["subject"], "scope": entree["scope"], "questions": entree["questions"]}
        for entree in couples.values()
        if entree["unanswered"] < threshold
    ]

    return {
        "measured_questions": sum(entree["questions"] for entree in couples.values()),
        "pairs_seen": len(couples),
        "gaps": manques,
        "covered": sorted(couverts, key=lambda entree: entree["subject"]),
        "threshold": threshold,
        "note": (
            "Un manque est un couple sujet × portée que de vraies questions ont "
            "touché sans réponse. Un manque que personne n'a demandé n'est pas un "
            "manque, c'est une supposition sur l'avenir."
        ),
    }


def gap_report(audit: Any = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """Rend la mesure des manques, prête à publier."""
    return detect_gaps(audit=audit, limit=limit or EVENEMENTS_LUS)
