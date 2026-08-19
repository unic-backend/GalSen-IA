"""
Le pipeline de recherche, et l'endroit exact où il s'arrête (R07.2, STEP 7).

## Les treize étapes de STEP 7, parcourues

```
INTENTION → PLANIFICATION → GÉNÉRATION DE REQUÊTES → ROUTAGE → RECHERCHE
→ RÉCUPÉRATION → NORMALISATION → VALIDATION → RECOUPEMENT → CONFIANCE
→ PROVENANCE → RAISONNEMENT → RÉPONSE
```

Ce module les parcourt et rend, pour chacune, ce qui s'est réellement passé. Il
**réutilise le vocabulaire d'issues de `creative/mvp.py`** — `OK`, `BLOCKED`,
`NOT_MEASURABLE`, `NOT_REACHED` — plutôt que d'en inventer un second : deux mots
pour un même état est la façon dont deux rapports finissent par se contredire.

## Ce qu'il ne fait pas, et pourquoi

**Il n'invente aucune requête.** La génération de requêtes part de la question
telle qu'écrite et des facettes **explicitement fournies**. Sans facette, il y a
une requête : la question, verbatim. Élargir une question avec des termes que
personne n'a demandés produirait des sources sur un sujet voisin, présentées
comme répondant à la question posée.

**Il n'exécute aucune recherche par lui-même.** La fonction de recherche est
**injectée**. Sans elle, l'étape est `BLOCKED` et le dit — au lieu d'appeler le
réseau depuis un module qui prétendrait ne faire que planifier.

**Il ne saute pas une étape bloquée.** Le premier blocage dur est l'endroit où
la chaîne s'arrête réellement ; ce qui suit est parcouru pour dire ce qu'il
ferait, jamais compté comme franchi. C'est la règle que `mvp.py` tient depuis
§21.

**Il ne rend jamais de réponse fabriquée.** Quand la chaîne s'arrête, la réponse
est `UNKNOWN` — STEP 5 l'exige, et `answer` reste `None`.

## STEP 15, tenu en code plutôt qu'en consigne

*« Les résultats de recherche ne doivent jamais devenir automatiquement des
instructions créatives. »* Le pipeline rend des **sources**, jamais un
`CreativeIntent`, et `separation_report()` nomme la frontière : comprendre,
chercher, planifier, créer, exécuter restent cinq choses.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..creative.mvp import BLOQUE, NON_ATTEINT, NON_MESURABLE, OK
from .routing import CHOISI, INCONNU, ResearchNeed, route
from .sources import ResearchSource, corroborate, normalize, propose_for_knowledge

#: Les treize étapes de STEP 7, dans l'ordre du texte.
ETAPES = (
    "user_intent",
    "research_planner",
    "query_generation",
    "provider_routing",
    "search",
    "source_retrieval",
    "source_normalization",
    "source_validation",
    "cross_source_comparison",
    "confidence",
    "provenance",
    "galsen_reasoning",
    "answer",
)

#: Ce qu'une fonction de recherche injectée doit rendre : une liste de dicts
#: portant au moins une `url`.
SearchFn = Callable[[str, str], Sequence[Dict[str, Any]]]


class PipelineRefused(ValueError):
    """Une demande de recherche impossible telle quelle."""


def _etape(name: str, outcome: str, detail: str, **preuve: Any) -> Dict[str, Any]:
    """Une étape parcourue, avec ce qui la prouve."""
    return {"step": name, "outcome": outcome, "detail": detail,
            "evidence": preuve}


def generate_queries(question: str,
                     facets: Sequence[str] = ()) -> List[str]:
    """
    Construit les requêtes à partir de ce qui a été demandé, et rien d'autre.

    Args:
        question: La question, telle qu'écrite.
        facets: Les facettes explicitement fournies par l'appelant.

    Returns:
        Les requêtes. Sans facette, **une seule** : la question verbatim.

    Raises:
        PipelineRefused: Si la question est vide.

    Note:
        Aucun terme n'est ajouté, aucun synonyme deviné, aucune traduction
        faite. Une question élargie par la plateforme ramènerait des sources sur
        un sujet voisin, présentées comme répondant à la question posée — ce que
        §6 de la directive précédente appelle inventer du contenu que personne
        n'a demandé.
    """
    propre = str(question or "").strip()
    if not propre:
        raise PipelineRefused(
            "Une question vide ne se planifie pas : il n'y a rien à chercher."
        )
    retenues = [propre]
    for facette in facets:
        texte = str(facette or "").strip()
        if not texte:
            continue
        # La comparaison porte sur la requête construite, pas sur la facette :
        # deux facettes distinctes peuvent produire la même requête, et deux
        # facettes identiques la produisent forcément.
        requete = f"{propre} {texte}"
        if requete not in retenues:
            retenues.append(requete)
    return retenues


def run_pipeline(question: str,
                 facets: Sequence[str] = (),
                 capability: str = "web_search",
                 search: Optional[SearchFn] = None,
                 source_type: str = "search_result",
                 commercial: bool = False,
                 carries_personal_data: bool = False) -> Dict[str, Any]:
    """
    Parcourt les treize étapes de STEP 7 et rapporte ce qui a eu lieu.

    Args:
        question: La question posée, conservée telle quelle.
        facets: Les facettes explicitement fournies.
        capability: La capacité de recherche visée.
        search: La fonction de recherche, injectée. `None` bloque l'étape de
            recherche plutôt que d'appeler le réseau depuis ici.
        source_type: La nature des sources attendues.
        commercial: Si le résultat sera exploité commercialement.
        carries_personal_data: Si la requête emporte la donnée d'une personne.

    Returns:
        Une entrée par étape, les comptes par issue, le premier blocage dur, les
        sources normalisées, et `answer` — **`None` tant que la chaîne ne va pas
        jusqu'au bout**.

    Raises:
        PipelineRefused: Question vide, ou capacité inconnue.
    """
    etapes: List[Dict[str, Any]] = []
    sources: Tuple[ResearchSource, ...] = ()

    #: 1. L'intention — conservée telle qu'écrite, jamais reformulée.
    requetes = generate_queries(question, facets)
    etapes.append(_etape(
        "user_intent", OK,
        "La question est conservée telle qu'écrite ; rien n'en est reformulé.",
        question=question, facets=list(facets)))

    #: 2. La planification — ce qui est cherché, et avec quelles contraintes.
    besoin = ResearchNeed(capability=capability, commercial=commercial,
                          carries_personal_data=carries_personal_data)
    etapes.append(_etape(
        "research_planner", OK,
        f"Une capacité visée — « {capability} » — et ses contraintes.",
        capability=capability, commercial=commercial,
        carries_personal_data=carries_personal_data))

    #: 3. Les requêtes — dérivées, jamais élargies.
    etapes.append(_etape(
        "query_generation", OK,
        f"{len(requetes)} requête(s), dérivée(s) de la question et des "
        "facettes fournies. Aucun terme ajouté.",
        queries=requetes))

    #: 4. Le routage.
    routage = route(besoin)
    routage_ok = routage["decision"] == CHOISI
    etapes.append(_etape(
        "provider_routing", OK if routage_ok else BLOQUE,
        routage["reason"] or f"Fournisseur retenu : {routage['provider_id']}.",
        decision=routage["decision"], provider_id=routage["provider_id"],
        plan=routage["plan"]))

    #: 5. La recherche — injectée, jamais appelée depuis ici.
    resultats: List[Dict[str, Any]] = []
    if not routage_ok:
        recherche_issue, recherche_detail = NON_ATTEINT, (
            "Le routage n'a retenu aucun fournisseur : rien n'est cherché.")
    elif search is None:
        recherche_issue, recherche_detail = BLOQUE, (
            "Aucune fonction de recherche fournie. Ce module ne joint pas le "
            "réseau lui-même : l'étape le dit au lieu de le faire.")
    else:
        try:
            for requete in requetes:
                resultats.extend(search(routage["provider_id"], requete))
            recherche_issue, recherche_detail = OK, (
                f"{len(resultats)} résultat(s) rapporté(s).")
        except Exception as erreur:                    # noqa: BLE001
            recherche_issue = BLOQUE
            recherche_detail = f"La recherche a échoué : {type(erreur).__name__}: {erreur}"
    etapes.append(_etape("search", recherche_issue, recherche_detail,
                         results=len(resultats)))

    chaine_vivante = recherche_issue == OK

    #: 6. La récupération du corps des sources.
    etapes.append(_etape(
        "source_retrieval",
        NON_MESURABLE if chaine_vivante else NON_ATTEINT,
        ("Aucun corps n'est récupéré ici : la récupération passe par le garde "
         "de `safety.py` et par un client qui n'est pas de ce module."
         if chaine_vivante else "Après le premier blocage."),
        bodies_fetched=0))

    #: 7. La normalisation.
    if chaine_vivante:
        normalisees = []
        refusees = []
        for brut in resultats:
            try:
                normalisees.append(normalize(
                    brut, provider=routage["provider_id"], query=question,
                    source_type=source_type))
            except Exception as erreur:                # noqa: BLE001
                refusees.append(str(erreur))
        sources = tuple(normalisees)
        etapes.append(_etape(
            "source_normalization", OK if sources else BLOQUE,
            f"{len(sources)} source(s) normalisée(s), {len(refusees)} refusée(s).",
            normalized=len(sources), refused=refusees))
        chaine_vivante = bool(sources)
    else:
        etapes.append(_etape("source_normalization", NON_ATTEINT,
                             "Après le premier blocage."))

    #: 8. La validation — l'état de chaque source, jamais promu ici.
    if chaine_vivante:
        etats = sorted({s.validation_status for s in sources})
        etapes.append(_etape(
            "source_validation", OK,
            f"Chaque source entre avec son état : {etats}. Aucune n'est "
            "promue par le seul fait d'avoir été trouvée.",
            states=etats))
    else:
        etapes.append(_etape("source_validation", NON_ATTEINT,
                             "Après le premier blocage."))

    #: 9. Le recoupement.
    recoupement: Optional[Dict[str, Any]] = None
    if chaine_vivante:
        recoupement = corroborate(sources)
        etapes.append(_etape(
            "cross_source_comparison", OK,
            f"{recoupement['distinct_sources']} source(s) distincte(s) sur "
            f"{recoupement['distinct_providers']} fournisseur(s) → "
            f"{recoupement['status']}.",
            **recoupement))
    else:
        etapes.append(_etape("cross_source_comparison", NON_ATTEINT,
                             "Après le premier blocage."))

    #: 10. La confiance — jamais un nombre inventé.
    etapes.append(_etape(
        "confidence",
        NON_MESURABLE if chaine_vivante else NON_ATTEINT,
        ("Aucune confiance chiffrée n'est produite : rien ici ne mesure la "
         "fiabilité d'une source, et un chiffre sans base se comporterait "
         "comme une mesure sans en être une."
         if chaine_vivante else "Après le premier blocage."),
        confidence=None))

    #: 11. La provenance.
    if chaine_vivante:
        etapes.append(_etape(
            "provenance", OK,
            "Chaque source porte ses dix champs de provenance et se projette "
            "vers le format d'acquisition existant.",
            provenance=[s.as_dict() for s in sources]))
    else:
        etapes.append(_etape("provenance", NON_ATTEINT,
                             "Après le premier blocage."))

    #: 12. Le raisonnement — il demande un modèle.
    etapes.append(_etape(
        "galsen_reasoning", NON_ATTEINT if not chaine_vivante else BLOQUE,
        ("Le raisonnement demande un fournisseur de modèle. Ce module n'en "
         "appelle aucun et n'en simule aucun."
         if chaine_vivante else "Après le premier blocage.")))

    #: 13. La réponse — jamais fabriquée.
    etapes.append(_etape(
        "answer", NON_ATTEINT,
        "Aucune réponse n'est produite : la chaîne ne va pas jusqu'au bout, et "
        "une réponse approchante serait pire que pas de réponse."))

    premier_blocage = next((e["step"] for e in etapes
                            if e["outcome"] == BLOQUE), None)
    comptes = {
        "ok": sum(1 for e in etapes if e["outcome"] == OK),
        "blocked": sum(1 for e in etapes if e["outcome"] == BLOQUE),
        "not_measurable": sum(1 for e in etapes if e["outcome"] == NON_MESURABLE),
        "not_reached": sum(1 for e in etapes if e["outcome"] == NON_ATTEINT),
    }
    return {
        "question": question,
        "queries": requetes,
        "steps": etapes,
        "counts": comptes,
        "first_block": premier_blocage,
        "sources": [s.as_dict() for s in sources],
        "corroboration": recoupement,
        "answer": None,
        "status": INCONNU,
        "knowledge_proposal": (propose_for_knowledge(sources)
                               if sources else None),
        "note": ("Aucune réponse n'est fabriquée, et rien n'entre dans la "
                 "connaissance : la proposition reste un DRAFT sous "
                 "approbation humaine."),
    }


def separation_report() -> Dict[str, Any]:
    """
    La frontière que STEP 15 demande, dite en code plutôt qu'en consigne.

    Returns:
        Les cinq activités séparées, et ce que le pipeline rend — des sources,
        jamais une intention créative.
    """
    return {
        "separated": ["UNDERSTANDING", "RESEARCH", "PLANNING", "CREATION",
                      "EXECUTION"],
        "pipeline_returns": ["sources", "provenance", "corroboration"],
        "pipeline_never_returns": ["CreativeIntent", "creative instructions",
                                   "fabricated answer"],
        "rules": [
            "Un résultat de recherche ne devient jamais automatiquement une "
            "instruction créative.",
            "Le CreativeEngine décide de ce qui est pertinent pour l'intention "
            "créative de la personne ; le pipeline ne le décide pas pour lui.",
            "Aucune recherche non liée n'est mêlée à une génération créative.",
        ],
    }


def pipeline_report() -> Dict[str, Any]:
    """
    Ce que le pipeline parcourt, et ce qu'il refuse.

    Returns:
        Les étapes déclarées et les règles tenues.
    """
    return {
        "steps": list(ETAPES),
        "count": len(ETAPES),
        "outcomes": [OK, BLOQUE, NON_MESURABLE, NON_ATTEINT],
        "shares_vocabulary_with": "creative/mvp.py",
        "rules": [
            "Aucune requête n'est élargie : la question part telle qu'écrite.",
            "La fonction de recherche est injectée ; ce module ne joint pas le "
            "réseau.",
            "Le premier blocage dur arrête la chaîne, et la suite est "
            "parcourue sans être comptée comme franchie.",
            "Aucune confiance chiffrée n'est produite.",
            "Aucune réponse n'est fabriquée : le statut est UNKNOWN.",
            "Rien n'entre dans la connaissance automatiquement.",
        ],
    }
