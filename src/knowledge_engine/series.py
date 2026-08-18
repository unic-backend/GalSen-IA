"""
Measured series: a number, the year it was measured, and nothing in between.

Population and GDP are the first worldwide series this repository carries. They
are the kind of knowledge that goes wrong quietly: a figure without its year
looks like a fact about today, and a gap filled by a straight line looks like a
measurement nobody took.

Four rules hold here, and each exists because of a specific way of being wrong.

**Nothing is interpolated, nothing is extrapolated.** A year the source does not
carry stays missing. Drawing a line between 2019 and 2023 would invent four
measurements, and they would be indistinguishable from the real ones the moment
they were written.

**A value is never served without its year.** "Senegal: 18.4 million" is a
sentence about no particular time. The year is not metadata here; it is half the
fact.

**An absent country answers UNKNOWN, never zero.** Zero is a measurement — it
means someone counted nobody. Using it for "not in the dataset" would be the
most confident possible way to be wrong.

**An aggregate is not a country.** World Bank series carry rows like `WLD`,
`ARB`, `EUU`. They are real and useful, and mixing them with countries would
make any count of "countries covered" false. They are separated by confronting
each code with the ISO 3166 set derived in phase 52.1 — not by a hand-written
list that would go stale.
"""

from __future__ import annotations

import csv
import io
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

INCONNU = "UNKNOWN"

#: Les séries acquises. `tier` est celui de **ce qui est récupéré** ; il n'hérite
#: jamais du rang de l'institution en amont — la Banque mondiale publie, ce
#: dépôt lit une redistribution.
SERIES_MONDIALES: Dict[str, Dict[str, Any]] = {
    "population": {
        "url": "https://raw.githubusercontent.com/datasets/population/main/data/population.csv",
        "file": "datasets-population.csv",
        "indicator": "SP.POP.TOTL",
        "unit": "habitants",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "Banque mondiale — World Development Indicators",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution) ; conditions de la Banque mondiale en amont",
    },
    "gdp": {
        "url": "https://raw.githubusercontent.com/datasets/gdp/main/data/gdp.csv",
        "file": "datasets-gdp.csv",
        "indicator": "NY.GDP.MKTP.CD",
        "unit": "USD courants",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "Banque mondiale — World Development Indicators",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution) ; conditions de la Banque mondiale en amont",
    },
}


class SeriesRefused(ValueError):
    """Une série inutilisable, avec sa raison."""


def _nombre(brut: str) -> Optional[float]:
    """
    Lit une valeur numérique, ou `None`.

    Une cellule vide n'est pas un zéro : c'est une mesure absente, et les
    confondre ferait apparaître un pays qui aurait disparu.
    """
    texte = str(brut or "").strip()
    if not texte:
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def read_series(
    contenu: str, codes_pays: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Lit une série depuis son CSV.

    Args:
        contenu: Le CSV, tel qu'acquis.
        codes_pays: Les codes ISO 3166-1 alpha-3 connus. Ce qui n'y figure pas
            est un **agrégat**, séparé et compté — jamais mêlé aux pays.

    Returns:
        Les séries par pays, les agrégats, et ce qui a été refusé.
    """
    lignes = list(csv.DictReader(io.StringIO(contenu)))
    connus = {code.upper() for code in (codes_pays or set())}

    pays: Dict[str, Dict[str, float]] = {}
    agregats: Dict[str, Dict[str, float]] = {}
    noms: Dict[str, str] = {}
    refusees = 0

    for ligne in lignes:
        code = str(ligne.get("Country Code", "") or "").strip().upper()
        annee = str(ligne.get("Year", "") or "").strip()
        valeur = _nombre(ligne.get("Value", ""))
        if not code or not annee.isdigit() or valeur is None:
            # Comptées : une série dont la taille s'explique par des lignes
            # disparues n'est pas vérifiable.
            refusees += 1
            continue

        cible = pays if (not connus or code in connus) else agregats
        cible.setdefault(code, {})[annee] = valeur
        noms.setdefault(code, str(ligne.get("Country Name", "") or "").strip())

    return {
        "countries": pays,
        "aggregates": agregats,
        "names": noms,
        "refused_rows": refusees,
        "rows": len(lignes),
    }


def latest(serie: Dict[str, float]) -> Tuple[Optional[str], Optional[float]]:
    """
    La dernière année **mesurée** d'une série.

    Ce n'est pas « l'année en cours » : c'est la dernière que la source porte.
    Les confondre ferait passer une mesure de 2023 pour une mesure d'aujourd'hui.

    Args:
        serie: La série `{année: valeur}`.

    Returns:
        L'année et la valeur, ou `(None, None)` si la série est vide.
    """
    if not serie:
        return None, None
    annee = max(serie, key=int)
    return annee, serie[annee]


def coverage(serie: Dict[str, float]) -> Dict[str, Any]:
    """
    Ce que la série couvre, et ce qui lui manque.

    Les années manquantes sont **nommées**, pas comblées : une série continue en
    apparence et trouée en réalité est la façon la plus discrète de mentir avec
    des chiffres.

    Args:
        serie: La série.

    Returns:
        Première et dernière année mesurées, nombre de points, années absentes.
    """
    if not serie:
        return {"first_year": INCONNU, "last_year": INCONNU, "points": 0,
                "missing_years": []}

    annees = sorted(int(a) for a in serie)
    attendues = set(range(annees[0], annees[-1] + 1))
    return {
        "first_year": str(annees[0]),
        "last_year": str(annees[-1]),
        "points": len(annees),
        "missing_years": [str(a) for a in sorted(attendues - set(annees))],
    }


def _provenance(cle: str) -> Dict[str, Any]:
    """La provenance d'une série, au format du dépôt."""
    serie = SERIES_MONDIALES[cle]
    return {
        "source": serie["publisher"],
        "source_url": serie["url"],
        "upstream_source": serie["upstream_source"],
        "upstream_tier": serie["upstream_tier"],
        "source_tier": serie["tier"],
        "licence": serie["licence"],
        "indicator": serie["indicator"],
        "unit": serie["unit"],
        "verification_status": "derived_from_source",
        "confidence": "derived",
    }


def build_series(
    contenus: Dict[str, str], codes_pays: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Construit les séries mondiales depuis les CSV acquis.

    Args:
        contenus: Le CSV de chaque série, par clé de `SERIES_MONDIALES`.
        codes_pays: Les codes ISO connus, pour distinguer pays et agrégats.

    Returns:
        Les séries, leur couverture et leurs agrégats.

    Raises:
        SeriesRefused: Si aucune série n'est exploitable. Un objet vide
            laisserait croire qu'aucune mesure n'existe.
    """
    connus = {str(code).upper() for code in (codes_pays or [])}
    series: Dict[str, Any] = {}

    for cle, contenu in contenus.items():
        if cle not in SERIES_MONDIALES:
            raise SeriesRefused(
                f"Série « {cle} » inconnue : déclarée nulle part dans "
                f"SERIES_MONDIALES ({', '.join(sorted(SERIES_MONDIALES))})."
            )
        lue = read_series(contenu, connus)
        series[cle] = {
            "provenance": _provenance(cle),
            "values": lue["countries"],
            "aggregates": sorted(lue["aggregates"]),
            "names": lue["names"],
            "counts": {
                "countries": len(lue["countries"]),
                "aggregates": len(lue["aggregates"]),
                "refused_rows": lue["refused_rows"],
                "rows": lue["rows"],
            },
        }

    if not any(serie["values"] for serie in series.values()):
        raise SeriesRefused(
            "Aucune mesure exploitable : les sources sont absentes ou n'ont pas "
            "la forme attendue. Un objet vide laisserait croire qu'aucune "
            "mesure n'existe."
        )

    return {
        "series": series,
        "built_from": {cle: SERIES_MONDIALES[cle]["file"] for cle in series},
        "rules": [
            "Rien n'est interpolé ni extrapolé : une année absente le reste, "
            "et les années manquantes sont nommées.",
            "Une valeur n'est jamais servie sans son année : l'année est la "
            "moitié du fait.",
            "Un pays absent rend UNKNOWN, jamais zéro — zéro est une mesure.",
            "Un agrégat n'est pas un pays : il est séparé et compté.",
        ],
    }


def answer_series(
    code: str, indicator: str, monde_series: Dict[str, Any],
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Répond une mesure, avec son année — ou `UNKNOWN`.

    Args:
        code: Le code ISO 3166-1 alpha-3 du pays.
        indicator: `population` ou `gdp`.
        monde_series: L'objet construit.
        year: Une année précise. Sans elle, la **dernière mesurée**.

    Returns:
        La valeur, son année, sa provenance, et la couverture de la série.
    """
    serie = (monde_series.get("series") or {}).get(indicator)
    if serie is None:
        return {
            "status": "UNKNOWN", "indicator": indicator,
            "reason": (
                f"Aucune série « {indicator} ». Séries disponibles : "
                f"{', '.join(sorted((monde_series.get('series') or {})))}."
            ),
        }

    cherche = str(code or "").strip().upper()
    valeurs = serie["values"].get(cherche)
    if not valeurs:
        agrege = cherche in set(serie.get("aggregates") or [])
        return {
            "status": "UNKNOWN", "indicator": indicator, "country": cherche,
            "reason": (
                f"« {cherche} » est un agrégat de la source, pas un pays."
                if agrege else
                f"Aucune mesure pour « {cherche} » dans cette série. Zéro n'est "
                "pas rendu : zéro serait une mesure."
            ),
        }

    if year:
        mesure = valeurs.get(str(year))
        if mesure is None:
            couverture = coverage(valeurs)
            return {
                "status": "UNKNOWN", "indicator": indicator, "country": cherche,
                "year": str(year),
                "reason": (
                    f"Aucune mesure pour {year}. Rien n'est interpolé : la "
                    f"série couvre {couverture['first_year']}–"
                    f"{couverture['last_year']}, "
                    f"{len(couverture['missing_years'])} année(s) manquante(s)."
                ),
                "coverage": couverture,
            }
        annee_rendue, valeur = str(year), mesure
    else:
        annee_rendue, valeur = latest(valeurs)

    return {
        "status": "FOUND",
        "indicator": indicator,
        "country": cherche,
        # L'année voyage avec la valeur, toujours : un chiffre sans son année
        # est une phrase sur aucun moment en particulier.
        "year": annee_rendue,
        "value": valeur,
        "unit": serie["provenance"]["unit"],
        # La portée n'est pas déduite ici : elle appartient au pays, et le pays
        # est porté par `world.answer_country`. La fabriquer depuis un code
        # alpha-3 tronqué donnerait des portées fausses (« GBR » → « gb » est
        # juste, « CHE » → « ch » aussi, « DEU » → « de » ne l'est pas).
        "coverage": coverage(valeurs),
        "provenance": serie["provenance"],
    }


def series_report(monde_series: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ce que les séries couvrent, et ce qu'elles ne font pas.

    Returns:
        Les comptes par série et les règles tenues.
    """
    series = monde_series.get("series") or {}
    return {
        "series": {
            cle: {
                **serie["counts"],
                "unit": serie["provenance"]["unit"],
                "indicator": serie["provenance"]["indicator"],
            }
            for cle, serie in series.items()
        },
        "built_from": monde_series.get("built_from", {}),
        "rules": monde_series.get("rules", []),
        "does_not": [
            "Combler une année manquante : ni interpolation, ni extrapolation.",
            "Rendre zéro pour une mesure absente.",
            "Mêler les agrégats aux pays.",
            "Prétendre que la dernière année mesurée est l'année en cours.",
        ],
    }


def known_country_codes(monde: Dict[str, Any]) -> List[str]:
    """
    Les codes ISO 3166-1 alpha-3 de la connaissance mondiale (phase 52.1).

    Args:
        monde: L'objet construit par `world.build_world_knowledge`.

    Returns:
        Les codes, pour distinguer un pays d'un agrégat sans liste écrite à la
        main — une liste écrite à la main vieillirait sans que rien ne le dise.
    """
    return sorted(
        pays["iso3"] for pays in monde.get("countries", [])
        if pays.get("iso3") and pays["iso3"] != INCONNU
    )


#: Là où les séries dérivées sont écrites par `scripts/build_world_knowledge.py`.
FICHIER_SERIES = os.path.join("data", "processed_global", "world_series.json")

#: Cache du fichier dérivé : 700 ko relus à chaque question coûteraient plus
#: cher que la question.
_CACHE_SERIES: Dict[str, Any] = {}


def load_series(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge les séries mesurées dérivées.

    Args:
        chemin: Le fichier. Celui du dépôt par défaut.

    Returns:
        L'objet dérivé, ou un objet **vide qui se déclare tel**. Des séries
        absentes ne sont pas des séries vides, et la différence doit se voir
        avant la première question.
    """
    cible = chemin or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        FICHIER_SERIES,
    )
    if cible in _CACHE_SERIES:
        return _CACHE_SERIES[cible]

    if not os.path.isfile(cible):
        vide = {
            "series": {}, "built": False,
            "reason": (
                "Les séries mesurées n'ont jamais été construites. "
                "`python scripts/build_world_knowledge.py` les dérive des jeux "
                "acquis. Absentes n'est pas vides."
            ),
        }
        _CACHE_SERIES[cible] = vide
        return vide

    with open(cible, "r", encoding="utf-8") as flux:
        series = json.load(flux)
    series["built"] = True
    _CACHE_SERIES[cible] = series
    return series
