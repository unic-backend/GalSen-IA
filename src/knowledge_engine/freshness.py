"""
Freshness: how old a figure is, said out loud, next to the figure.

A knowledge base does not usually become wrong all at once. It becomes wrong the
way a printed almanac does — slowly, silently, while every individual page still
looks correct. The population figure that was right in 2024 is still *the same
number* in 2030; what changed is what it means to serve it without saying when it
was measured.

Three rules.

**A stale value is served with its age, never replaced and never hidden.**
Replacing it with something newer-sounding would be fabrication; hiding it would
leave the question unanswered when a real, dated measurement exists. The answer
is the measurement plus its age, and the reader decides.

**Age is measured against the cadence of the thing, not against a single
threshold.** Population is published once a year, and the year that just ended is
not published yet: a 2024 figure read in 2026 is normal, not late. A rule that
called it stale would cry wolf on every series in the repository, and an alarm
that is always on is an alarm nobody reads.

**What cannot be dated is `UNKNOWN`, not fresh.** A figure with no year is the
most dangerous kind: it reads as current. Absence of a date is never treated as
evidence of recency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

INCONNU = "UNKNOWN"


class Freshness(str, Enum):
    """L'âge d'une mesure, rapporté à la cadence de ce qu'elle mesure."""

    #: Aussi récente que la source peut l'être.
    FRESH = "FRESH"

    #: Plus vieille que prévu, encore utilisable — servie avec son âge.
    AGING = "AGING"

    #: Nettement en retard sur la cadence. Toujours servie, toujours datée.
    STALE = "STALE"

    #: Sans date. Ce n'est **pas** « récente ».
    UNKNOWN = "UNKNOWN"


#: Cadence attendue de chaque indicateur, en années, et le retard normal de
#: publication. Une statistique annuelle n'est pas publiée le 1er janvier :
#: l'année écoulée met environ un an à sortir. Traiter ce délai comme un retard
#: ferait sonner l'alarme sur toutes les séries du dépôt — et une alarme
#: toujours allumée n'est plus lue.
CADENCES: Dict[str, Dict[str, int]] = {
    "population": {"period_years": 1, "publication_lag_years": 1},
    "gdp": {"period_years": 1, "publication_lag_years": 1},
}

#: Cadence retenue pour un indicateur non déclaré. Volontairement large : se
#: tromper vers l'indulgence produit un « AGING » discutable, se tromper vers la
#: sévérité produit un « STALE » faux, qui ferait jeter une mesure valide.
CADENCE_PAR_DEFAUT = {"period_years": 1, "publication_lag_years": 2}

#: Années au-delà de la tolérance à partir desquelles une mesure est dite
#: `STALE` plutôt que `AGING`.
MARGE_AVANT_PEREMPTION = 2


def _annee_courante(now: Optional[datetime] = None) -> int:
    """L'année en cours, en UTC."""
    instant = now if now is not None else datetime.now(timezone.utc)
    return instant.year


def cadence_of(indicator: str) -> Dict[str, int]:
    """
    La cadence déclarée d'un indicateur, ou le défaut.

    Args:
        indicator: L'indicateur.

    Returns:
        Période et retard de publication attendus, en années.
    """
    return CADENCES.get(indicator, CADENCE_PAR_DEFAUT)


def freshness_of_year(
    year: Any, indicator: str = "", now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Mesure l'âge d'une valeur datée par son année.

    Args:
        year: L'année de la mesure.
        indicator: L'indicateur, pour connaître sa cadence.
        now: L'instant de référence, pour les tests. Le temps vient de
            l'appelant : une fonction qui lit l'horloge en douce ne se teste
            qu'en attendant.

    Returns:
        L'âge en années, le verdict, et la raison en clair.
    """
    texte = str(year or "").strip()
    if not texte.isdigit():
        return {
            "status": Freshness.UNKNOWN.value,
            "age_years": INCONNU,
            "reason": (
                "Mesure sans année : son âge est inconnu. Une valeur non datée "
                "n'est pas récente — elle en a seulement l'air."
            ),
        }

    cadence = cadence_of(indicator)
    tolerance = cadence["period_years"] + cadence["publication_lag_years"]
    age = _annee_courante(now) - int(texte)

    if age <= tolerance:
        verdict, raison = Freshness.FRESH, (
            f"Mesure de {texte}, {age} an(s) : c'est ce que la source peut "
            f"offrir de plus récent (publication annuelle, environ "
            f"{cadence['publication_lag_years']} an de décalage)."
        )
    elif age <= tolerance + MARGE_AVANT_PEREMPTION:
        verdict, raison = Freshness.AGING, (
            f"Mesure de {texte}, {age} an(s) : plus ancienne que la cadence "
            "attendue. Elle est servie telle quelle, avec son âge."
        )
    else:
        verdict, raison = Freshness.STALE, (
            f"Mesure de {texte}, {age} an(s) : nettement en retard sur la "
            "cadence attendue. Elle reste rendue — la remplacer par une valeur "
            "plus récente d'apparence serait une fabrication."
        )

    return {
        "status": verdict.value,
        "age_years": age,
        "measured_year": texte,
        "expected_within_years": tolerance,
        "reason": raison,
    }


def freshness_of_series(
    serie: Dict[str, Any], indicator: str, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Mesure la fraîcheur d'une série entière, et **ce qui traîne dedans**.

    Une série peut atteindre 2024 tout en laissant des pays à 2015. La moyenne
    cacherait ces pays ; ils sont donc nommés. Un pays en retard sur ses pairs
    est un fait mesurable, pas un jugement.

    Args:
        serie: La série construite (`values` par pays).
        indicator: L'indicateur.
        now: L'instant de référence.

    Returns:
        La dernière année de la série, sa fraîcheur, et les pays en retard.
    """
    valeurs: Dict[str, Dict[str, float]] = serie.get("values") or {}
    dernieres = {
        code: max(mesures, key=int)
        for code, mesures in valeurs.items() if mesures
    }
    if not dernieres:
        return {
            "indicator": indicator,
            "status": Freshness.UNKNOWN.value,
            "reason": "Série vide : aucune année à dater.",
            "behind": [],
        }

    derniere_serie = max(dernieres.values(), key=int)
    fraicheur = freshness_of_year(derniere_serie, indicator, now)

    retard: List[Dict[str, Any]] = [
        {"country": code, "last_year": annee,
         "years_behind": int(derniere_serie) - int(annee)}
        for code, annee in sorted(dernieres.items())
        if int(derniere_serie) - int(annee) > cadence_of(indicator)["period_years"]
    ]

    return {
        "indicator": indicator,
        "series_last_year": derniere_serie,
        "status": fraicheur["status"],
        "age_years": fraicheur["age_years"],
        "reason": fraicheur["reason"],
        "countries": len(dernieres),
        # Nommés, pas moyennés : une moyenne cacherait exactement ceux qu'il
        # faut voir.
        "behind": sorted(retard, key=lambda e: -e["years_behind"])[:25],
        "behind_count": len(retard),
    }


def freshness_report(
    monde_series: Dict[str, Any], now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    La fraîcheur de toutes les séries chargées.

    Args:
        monde_series: L'objet construit par `series.build_series`.
        now: L'instant de référence.

    Returns:
        Un verdict par série, et ce que cette couche ne fait pas.
    """
    series = monde_series.get("series") or {}
    return {
        "measured_at_year": _annee_courante(now),
        "series": {
            cle: freshness_of_series(serie, cle, now)
            for cle, serie in series.items()
        },
        "cadences": {cle: cadence_of(cle) for cle in series},
        "rules": [
            "Une valeur périmée est servie **avec son âge** : ni remplacée, ni "
            "cachée. La remplacer serait une fabrication ; la cacher laisserait "
            "sans réponse une question qu'une mesure datée sait éclairer.",
            "L'âge se mesure contre la cadence de la chose, pas contre un seuil "
            "unique : une statistique annuelle a environ un an de décalage de "
            "publication, et ce n'est pas un retard.",
            "Ce qui n'est pas datable vaut UNKNOWN, jamais « récent ».",
        ],
        "does_not": [
            "Rafraîchir quoi que ce soit : aucune source n'est activée, et "
            "aucune acquisition n'a lieu ici.",
            "Supprimer une mesure ancienne.",
            "Estimer la valeur d'aujourd'hui à partir des précédentes.",
        ],
    }
