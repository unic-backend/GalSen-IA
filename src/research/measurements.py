"""
Ce qui est mesuré, et ce qui ne peut pas l'être (R10, STEP 13 et STEP 14).

## STEP 13 nomme huit mesures. Trois seulement sont possibles ici.

*« Ne pas prétendre à une amélioration de performance sans mesure. »* La
conséquence honnête de cette phrase est que **la plupart des colonnes restent
vides**, et qu'elles le disent :

| Mesure demandée | État | Pourquoi |
|---|---|---|
| Latence de recherche | `NOT_MEASURED` | aucun fournisseur ne tourne ici |
| Latence de récupération | `NOT_MEASURED` | idem, et rien dans cette couche ne récupère |
| Taux d'échec des fournisseurs | `NOT_MEASURED` | il faudrait des appels réels, sur une durée |
| Taux de repli | `NOT_MEASURED` | idem |
| Réseau | `NOT_MEASURED` | aucune requête n'est émise |
| **Surcoût d'orchestration** | **mesuré** | routage, normalisation, garde d'URL |
| **Taux de succès du cache** | **mesuré** | sur un exercice déclaré, pas sur du trafic |
| **Mémoire et processeur** | **mesurés** | de la machine, pas d'une recherche |

Le taux de succès du cache mérite sa précision : il est mesuré sur **un exercice
synthétique**, pas sur du trafic réel. Un taux mesuré sur des clés qu'on vient
d'écrire soi-même dit quelque chose du cache et **rien** de l'usage. Le rapport
le nomme plutôt que de laisser le chiffre parler à sa place.

## STEP 14 : le fournisseur reste un détail d'implémentation

*« L'utilisateur ne devrait pas avoir à savoir quel fournisseur est utilisé. »*
Ce n'est pas une intention, c'est une propriété des signatures : `run_pipeline`
prend une question et une **capacité**, jamais un fournisseur.
`transparency_report()` le vérifie par introspection plutôt que de l'affirmer.
"""

from __future__ import annotations

import inspect
import os
import time
from typing import Any, Callable, Dict, List

#: Rendu par toute mesure qu'on ne peut pas faire ici.
NON_MESURE = "NOT_MEASURED"


def _chronometre(operation: Callable[[], Any], repetitions: int = 100
                 ) -> float:
    """
    Mesure une opération, en millisecondes par appel.

    Args:
        operation: Ce qui est mesuré.
        repetitions: Le nombre d'appels. Le premier est fait à part, pour ne pas
            mesurer l'import du module en même temps que l'opération.

    Returns:
        La durée moyenne, en millisecondes.
    """
    operation()
    debut = time.perf_counter()
    for _ in range(repetitions):
        operation()
    return round((time.perf_counter() - debut) / repetitions * 1000, 4)


def orchestration_overhead() -> Dict[str, float]:
    """
    Le coût de l'orchestration elle-même, sans aucun appel sortant.

    Returns:
        Une durée par opération, en millisecondes. Ce sont les seules latences
        que cette couche peut honnêtement rendre : elles ne disent rien de la
        vitesse d'une recherche, seulement de ce que coûte de décider.
    """
    from .cache import ResearchCache
    from .pipeline import generate_queries, run_pipeline
    from .routing import ResearchNeed, route
    from .safety import as_data, check_url
    from .sources import normalize

    cache = ResearchCache(stale_after_seconds=60)
    cache.put_results("p", "web_search", "q", [1])
    brut = {"url": "https://exemple.test/a", "title": "A"}

    return {
        "route_web_search_ms": _chronometre(
            lambda: route(ResearchNeed("web_search")), 50),
        "generate_queries_ms": _chronometre(
            lambda: generate_queries("une question", ("a", "b")), 1000),
        "normalize_source_ms": _chronometre(
            lambda: normalize(brut, "p", "q", "web_page"), 500),
        "check_url_literal_ms": _chronometre(
            lambda: check_url("https://exemple.test/a", resolve=False), 1000),
        "wrap_as_data_ms": _chronometre(
            lambda: as_data("un contenu", "https://exemple.test/a"), 500),
        "cache_lookup_ms": _chronometre(
            lambda: cache.lookup("search_results", "p", "web_search", "q"),
            1000),
        "pipeline_without_search_ms": _chronometre(
            lambda: run_pipeline("une question"), 20),
    }


def cache_hit_rate(entries: int = 50) -> Dict[str, Any]:
    """
    Le taux de succès du cache, sur un exercice **déclaré synthétique**.

    Args:
        entries: Le nombre d'entrées écrites puis relues.

    Returns:
        Les comptes et le taux, avec la mention que l'exercice ne dit rien de
        l'usage réel.

    Note:
        Un taux mesuré sur des clés qu'on vient d'écrire soi-même est
        nécessairement proche de 1 pour les clés écrites et de 0 pour les
        autres. Ce qu'il vérifie est que **le cache distingue bien les deux**,
        pas qu'il serait utile en production.
    """
    from .cache import ResearchCache

    cache = ResearchCache(stale_after_seconds=3600)
    for indice in range(entries):
        cache.put_results("p", "web_search", f"requete-{indice}", [indice])

    succes = sum(
        1 for indice in range(entries)
        if cache.lookup("search_results", "p", "web_search",
                        f"requete-{indice}")["hit"])
    echecs = sum(
        1 for indice in range(entries)
        if cache.lookup("search_results", "p", "web_search",
                        f"absente-{indice}")["hit"])

    return {
        "entries_written": entries,
        "hits_on_written": succes,
        "hits_on_absent": echecs,
        "hit_rate_on_written": round(succes / entries, 3) if entries else None,
        "synthetic": True,
        "note": ("Exercice synthétique : les clés viennent d'être écrites. Il "
                 "vérifie que le cache distingue présent et absent, et ne dit "
                 "rien du taux qu'aurait un usage réel."),
    }


def machine() -> Dict[str, Any]:
    """
    Ce que la machine porte, mesuré et non supposé.

    Returns:
        Cœurs et mémoire quand ils sont lisibles, `NOT_MEASURED` sinon.
    """
    coeurs = os.cpu_count()
    memoire: Any = NON_MESURE
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        taille = os.sysconf("SC_PAGE_SIZE")
        memoire = round(pages * taille / (1024 ** 3), 1)
    except (ValueError, OSError, AttributeError):
        memoire = NON_MESURE
    return {
        "cpu_cores": coeurs if coeurs else NON_MESURE,
        "memory_gib": memoire,
        "gpu": NON_MESURE,
        "note": ("Mesures de la machine, pas d'une recherche. Aucune requête "
                 "n'a été émise pour les obtenir."),
    }


def transparency_report() -> Dict[str, Any]:
    """
    STEP 14, vérifié par introspection plutôt qu'affirmé.

    Returns:
        Pour chaque point d'entrée public, s'il expose un fournisseur dans sa
        signature. Aucun ne doit.
    """
    from .pipeline import run_pipeline
    from .routing import execute_with_fallback, route

    points = {
        "run_pipeline": run_pipeline,
        "route": route,
        "execute_with_fallback": execute_with_fallback,
    }
    expose = {}
    for nom, fonction in points.items():
        parametres = list(inspect.signature(fonction).parameters)
        expose[nom] = [p for p in parametres
                       if "provider" in p or "fournisseur" in p]

    return {
        "entry_points": {nom: list(inspect.signature(f).parameters)
                         for nom, f in points.items()},
        "exposing_a_provider": {nom: p for nom, p in expose.items() if p},
        "provider_is_an_implementation_detail": all(not p
                                                    for p in expose.values()),
        "note": ("Le fournisseur retenu est **rendu** dans le résultat — pour "
                 "la provenance et le diagnostic — mais aucun appelant n'a "
                 "besoin de le choisir."),
    }


def measurements_report() -> Dict[str, Any]:
    """
    Le relevé complet de STEP 13, mesures faites et mesures impossibles.

    Returns:
        Ce qui a été mesuré, et ce qui rend `NOT_MEASURED` avec sa raison.
    """
    impossibles: List[Dict[str, str]] = [
        {"measurement": "search_latency", "state": NON_MESURE,
         "reason": "Aucun fournisseur de recherche ne tourne ici : les deux "
                   "candidats sont BLOCKED."},
        {"measurement": "fetch_latency", "state": NON_MESURE,
         "reason": "Cette couche ne récupère aucune page ; la récupération "
                   "appartient à l'appelant."},
        {"measurement": "provider_failure_rate", "state": NON_MESURE,
         "reason": "Il faudrait des appels réels sur une durée. Aucun appel "
                   "n'a été émis."},
        {"measurement": "fallback_rate", "state": NON_MESURE,
         "reason": "Même raison : un taux sans trafic est un chiffre inventé."},
        {"measurement": "network_usage", "state": NON_MESURE,
         "reason": "Aucune requête réseau n'est émise par cette couche."},
    ]
    return {
        "measured": {
            "orchestration_overhead_ms": orchestration_overhead(),
            "cache": cache_hit_rate(),
            "machine": machine(),
        },
        "not_measured": impossibles,
        "measured_count": 3,
        "not_measured_count": len(impossibles),
        "transparency": transparency_report(),
        "rules": [
            "Aucune amélioration de performance n'est revendiquée : rien n'a "
            "été comparé à un avant.",
            "Les latences rendues sont celles de l'orchestration, jamais "
            "celles d'une recherche.",
            "Le taux de cache est déclaré synthétique là où il est rendu.",
            "Une mesure impossible rend NOT_MEASURED avec sa raison, jamais "
            "zéro.",
        ],
    }
