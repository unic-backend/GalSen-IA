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
    La cadence déclarée d'un indicateur ou d'un genre, ou le défaut.

    Les deux tables sont consultées : une série (`population`) et un genre de
    connaissance (`administrative_boundaries`) sont deux façons de nommer la
    même chose — la vitesse à laquelle ce qu'on mesure change. Les séparer en
    deux fonctions ferait vieillir une limite administrative au rythme d'une
    statistique annuelle, qui est faux de cinq ans.

    Args:
        indicator: L'indicateur ou le genre.

    Returns:
        Période et retard de publication attendus, en années.
    """
    if indicator in CADENCES:
        return CADENCES[indicator]
    return CADENCES_PAR_GENRE.get(indicator, CADENCE_PAR_DEFAUT)


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


#: Cadence attendue par **genre** de connaissance dérivée. Une limite
#: administrative ne vieillit pas comme une statistique annuelle : les découpages
#: changent, mais rarement — et un corpus de langue ne se périme pas du tout de
#: cette façon. Un seuil unique traiterait les trois pareil, et se tromperait
#: deux fois sur trois.
CADENCES_PAR_GENRE: Dict[str, Dict[str, int]] = {
    # Les régions et départements changent par décret. C'est rare, ce n'est pas
    # jamais : ce dépôt porte précisément une revendication de 46ᵉ département
    # non vérifiée, qui est **exactement** l'allure d'un découpage périmé.
    "administrative_boundaries": {"period_years": 5, "publication_lag_years": 1},
    # Codes ISO et régions M49 : stables, révisés de loin en loin.
    "country_reference": {"period_years": 5, "publication_lag_years": 1},
    # Statistiques annuelles.
    "statistics": {"period_years": 1, "publication_lag_years": 1},
    # Un corpus de langue ne se périme pas comme un chiffre. Son risque n'est
    # pas l'âge, c'est la **relecture** : le dire ici évite de faire sonner une
    # alarme qui n'a pas de sens, et d'oublier celle qui en a une.
    "language_corpus": {"period_years": 10, "publication_lag_years": 1},
}


def _annee_de(horodatage: Any) -> Optional[int]:
    """L'année d'un horodatage ISO, ou `None` s'il n'en est pas un."""
    texte = str(horodatage or "").strip()
    if len(texte) >= 4 and texte[:4].isdigit():
        return int(texte[:4])
    return None


def asset_freshness(
    name: str,
    built_at: Any = None,
    content_year: Any = None,
    kind: str = "",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    L'âge d'une connaissance dérivée, en **distinguant deux âges**.

    `built_at` dit quand la dérivation a tourné ; il ne dit **rien** de l'âge des
    faits. Relancer le script hier rend `built_at` d'hier alors que les mesures
    peuvent dater de 2011. Les confondre est la façon la plus efficace de faire
    passer une base périmée pour fraîche — et c'est la confusion que ce module
    existe pour empêcher.

    Le verdict rendu est **le pire des deux**, et il dit lequel.

    Args:
        name: Le nom de la connaissance.
        built_at: Quand la dérivation a été faite.
        content_year: L'année des faits eux-mêmes, si elle est connue.
        kind: Le genre, pour sa cadence.
        now: L'instant de référence.

    Returns:
        Les deux âges, le verdict retenu, et lequel des deux le porte.
    """
    cadence = cadence_of(kind)
    tolerance = cadence["period_years"] + cadence["publication_lag_years"]
    courante = _annee_courante(now)

    annee_build = _annee_de(built_at)
    age_derivation = courante - annee_build if annee_build is not None else None

    verdict_contenu = (
        freshness_of_year(content_year, kind, now) if content_year
        else {"status": Freshness.UNKNOWN.value, "age_years": INCONNU,
              "reason": "Âge des faits inconnu : la source ne les date pas."}
    )

    ordre = {
        Freshness.FRESH.value: 0, Freshness.AGING.value: 1,
        Freshness.STALE.value: 2, Freshness.UNKNOWN.value: 3,
    }
    if age_derivation is None:
        verdict_derivation = {
            "status": Freshness.UNKNOWN.value, "age_years": INCONNU,
            "reason": "Dérivation non datée : on ne sait pas quand elle a tourné.",
        }
    elif age_derivation <= tolerance:
        verdict_derivation = {
            "status": Freshness.FRESH.value, "age_years": age_derivation,
            "reason": f"Dérivée il y a {age_derivation} an(s), dans la cadence.",
        }
    elif age_derivation <= tolerance + MARGE_AVANT_PEREMPTION:
        verdict_derivation = {
            "status": Freshness.AGING.value, "age_years": age_derivation,
            "reason": f"Dérivée il y a {age_derivation} an(s) : à refaire bientôt.",
        }
    else:
        verdict_derivation = {
            "status": Freshness.STALE.value, "age_years": age_derivation,
            "reason": f"Dérivée il y a {age_derivation} an(s) : à refaire.",
        }

    porte = (
        "content" if ordre[verdict_contenu["status"]] >= ordre[verdict_derivation["status"]]
        else "derivation"
    )
    retenu = verdict_contenu if porte == "content" else verdict_derivation

    return {
        "asset": name,
        "kind": kind or INCONNU,
        "status": retenu["status"],
        "verdict_from": porte,
        "derivation": verdict_derivation,
        "content": verdict_contenu,
        "expected_within_years": tolerance,
        "note": (
            "`built_at` date la dérivation, pas les faits. Relancer le script "
            "rajeunit l'un sans toucher l'autre."
        ),
    }


#: Les connaissances dérivées que ce dépôt porte, et leur genre. Déclarées ici
#: parce qu'un genre ne se devine pas d'un nom de fichier : `senegal_master`
#: contient des limites administratives, `official_wolof_corpus` un corpus de
#: langue, et les traiter pareil ferait sonner une alarme sans objet sur l'un et
#: taire celle qui compte sur l'autre.
CONNAISSANCES_DERIVEES: Dict[str, Dict[str, str]] = {
    "senegal_master": {
        "path": "data/processed_senegal/senegal_master_knowledge.json",
        "kind": "administrative_boundaries",
        "what": "14 régions et 45 départements, dérivés de geoBoundaries",
    },
    "senegal_domains": {
        "path": "data/processed_senegal/senegal_domain_knowledge.json",
        "kind": "statistics",
        "what": "8 jeux sectoriels sénégalais",
    },
    "wolof_corpus": {
        "path": "data/processed_wolof/official_wolof_corpus.json",
        "kind": "language_corpus",
        "what": "2105 phrases wolof, orthographe CLAD",
    },
    "world_countries": {
        "path": "data/processed_global/world_countries.json",
        "kind": "country_reference",
        "what": "249 pays, codes ISO et taxonomie M49",
    },
    "world_series": {
        "path": "data/processed_global/world_series.json",
        "kind": "statistics",
        "what": "population et PIB par pays",
    },
}


def _racine_depot() -> str:
    """La racine du dépôt."""
    import os

    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repository_freshness(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    L'âge de **tout** ce que ce dépôt a dérivé.

    Lit les fichiers réellement présents ; un fichier absent est dit absent, pas
    supposé frais. C'est la question qu'un opérateur pose une fois par an et à
    laquelle personne ne pouvait répondre : « qu'est-ce qui, ici, est vieux ? »

    Args:
        now: L'instant de référence.

    Returns:
        Un verdict par connaissance, et ce qui manque.
    """
    import json
    import os

    verdicts = []
    absents = []
    for nom, declaration in sorted(CONNAISSANCES_DERIVEES.items()):
        chemin = os.path.join(_racine_depot(), declaration["path"])
        if not os.path.isfile(chemin):
            absents.append({"asset": nom, "path": declaration["path"],
                            "reason": "Fichier absent : jamais dérivé ici."})
            continue

        with open(chemin, "r", encoding="utf-8") as flux:
            objet = json.load(flux)

        verdicts.append({
            **asset_freshness(
                nom, built_at=objet.get("built_at"),
                content_year=_annee_du_contenu(objet),
                kind=declaration["kind"], now=now,
            ),
            "what": declaration["what"],
            "path": declaration["path"],
        })

    par_statut: Dict[str, int] = {}
    for verdict in verdicts:
        par_statut[verdict["status"]] = par_statut.get(verdict["status"], 0) + 1

    return {
        "assets": verdicts,
        "missing": absents,
        "by_status": dict(sorted(par_statut.items())),
        "rules": [
            "`built_at` date la dérivation, pas les faits : relancer un script "
            "rajeunit l'un sans toucher l'autre, et les confondre ferait passer "
            "une base périmée pour fraîche.",
            "Le verdict retenu est le **pire** des deux âges, et il dit lequel "
            "le porte.",
            "Chaque genre a sa cadence : une limite administrative ne vieillit "
            "pas comme une statistique annuelle.",
        ],
        "does_not": [
            "Rafraîchir quoi que ce soit : aucune source n'est activée.",
            "Supposer qu'un fichier absent est à jour.",
        ],
    }


def _annee_du_contenu(objet: Dict[str, Any]) -> Optional[str]:
    """
    L'année des **faits** portés par une connaissance dérivée, si elle est là.

    Cherchée dans les endroits où ce dépôt la met déjà, jamais devinée : une
    année inventée ici rendrait le verdict pire que l'absence de verdict.
    """
    series = objet.get("series")
    if isinstance(series, dict) and series:
        annees = [
            max(mesures, key=int)
            for serie in series.values()
            for mesures in (serie.get("values") or {}).values() if mesures
        ]
        if annees:
            return max(annees, key=int)

    domaines = objet.get("domains")
    if isinstance(domaines, dict):
        annees = [
            str(element["year"])
            for domaine in domaines.values()
            for element in (domaine.get("items") or [])
            if str(element.get("year", "")).isdigit()
        ]
        if annees:
            return max(annees, key=int)

    for cle in ("content_year", "data_year", "reference_year"):
        if objet.get(cle):
            return str(objet[cle])

    # Rien trouvé : `None`, et le verdict sera `UNKNOWN`. C'est un résultat, pas
    # un échec — il dit que la plateforme ne sait pas dater ces faits, ce qui
    # est vrai des limites administratives (geoBoundaries ne publie pas de date
    # par fichier) et d'un corpus de langue.
    return None
