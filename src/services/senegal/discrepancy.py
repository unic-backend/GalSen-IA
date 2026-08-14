"""
Deux sources, deux découpages : la comparaison, sans arbitrage.

Le découpage administratif du Sénégal n'est pas le même selon la source. Ce
module met les versions côte à côte, entité par entité, et **ne tranche
jamais** : décider laquelle a raison demande une source sénégalaise officielle,
et aucune n'est joignable depuis cet environnement.

## Les statuts, et ce que chacun autorise à faire

| Statut | Ce qu'il dit | Ce qu'il n'autorise pas |
|---|---|---|
| `MATCH` | Les deux sources portent l'entité | — |
| `MISSING_IN_SOURCE_B` | A la porte, B non | En conclure que B a tort |
| `MISSING_IN_SOURCE_A` | B la porte, A non | En conclure que A est incomplète |
| `CONFLICT` | Les deux la portent avec des valeurs différentes | Choisir la plus récente |
| `UNKNOWN` | La comparaison n'a pas pu être faite | Compter cela comme un accord |

## Le cas qui a motivé ce module

La directive du projet annonçait **46 départements** ; la source acquise en porte
**45**. Ce n'est ni une erreur de lecture, ni une source défaillante : ce sont
deux affirmations, dont une seule est adossée à des données ici. Le statut est
donc `UNKNOWN`, avec le blocage exact — et non `CONFLICT`, qui supposerait
qu'une source B existe et dit 46.

Forcer le jeu de données à 46 aurait été la fabrication la plus facile de tout
ce chantier, et la plus invisible.
"""

import json
import os
from typing import Any, Dict, List, Optional

#: Les statuts d'une comparaison. Aucun ne veut dire « résolu ».
MATCH = "MATCH"
CONFLIT = "CONFLICT"
ABSENT_DE_A = "MISSING_IN_SOURCE_A"
ABSENT_DE_B = "MISSING_IN_SOURCE_B"
INCONNU = "UNKNOWN"

#: Fichier de subdivisions ISO acquis par `scripts/ingest_senegal_domains.py`.
ISO_3166_2 = os.path.join("data", "raw_senegal", "iso-3166-2.json")


def _racine() -> str:
    """Retourne la racine du dépôt."""
    ici = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(ici)))


def _normalise(nom: str) -> str:
    """Retourne la forme comparable d'un nom de lieu."""
    from ...text_normalization import strip_accents

    return strip_accents(str(nom or "").strip().lower()).replace("-", " ")


def load_iso_subdivisions(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge les subdivisions ISO 3166-2 acquises, ou dit qu'elles manquent.

    Returns:
        Les divisions et leur provenance. **`available: false` n'est pas zéro
        subdivision** : c'est un fichier absent, et la distinction décide de
        l'action.
    """
    cible = chemin or os.path.join(_racine(), ISO_3166_2)
    if not os.path.isfile(cible):
        return {
            "available": False,
            "divisions": {},
            "reason": (
                f"Subdivisions ISO absentes : {cible}. Les acquérir avec "
                "`python scripts/ingest_senegal_domains.py`."
            ),
        }
    with open(cible, "r", encoding="utf-8") as fichier:
        donnees = json.load(fichier)
    return {
        "available": True,
        "divisions": (donnees.get("SN") or {}).get("divisions", {}),
        "source": "olahol/iso-3166-2.json (redistribution de ISO 3166-2)",
        "source_url": (
            "https://raw.githubusercontent.com/olahol/iso-3166-2.json/master/"
            "iso-3166-2.json"
        ),
        "source_tier": "TIER_C_SECONDARY",
        "upstream_source": "ISO 3166-2 — subdivisions",
        "version": INCONNU,
        "version_note": (
            "La redistribution ne porte aucune date de version. Une liste ISO "
            "sans date ne permet pas de dire si elle est ancienne ou si elle "
            "diverge — et ces deux cas demandent des actions différentes."
        ),
    }


def compare_regions(
    connaissance: Dict[str, Any], iso: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compare les régions de geoBoundaries et les subdivisions ISO 3166-2.

    Returns:
        Une ligne par entité, avec son statut et la provenance des deux côtés.
        **Aucun conflit n'est résolu** : quand les deux découpages divergent, les
        deux valeurs sont rendues.
    """
    iso = iso or load_iso_subdivisions()
    regions = {_normalise(r["name"]): r for r in connaissance["regions"]}

    if not iso["available"]:
        return {
            "comparable": False,
            "reason": iso["reason"],
            "rows": [
                {
                    "entity": region["name"], "source_a": region["name"],
                    "source_b": INCONNU, "status": INCONNU,
                    "provenance_a": region["provenance"]["source"],
                    "provenance_b": INCONNU,
                }
                for region in connaissance["regions"]
            ],
        }

    subdivisions = {_normalise(nom): (code, nom) for code, nom in iso["divisions"].items()}
    lignes = []

    for cle, region in sorted(regions.items()):
        correspondance = subdivisions.get(cle)
        lignes.append({
            "entity": region["name"],
            "source_a": region["name"],
            "source_b": correspondance[1] if correspondance else INCONNU,
            "iso_code_a": region.get("iso_code", INCONNU),
            "iso_code_b": correspondance[0] if correspondance else INCONNU,
            "status": MATCH if correspondance else ABSENT_DE_B,
            "provenance_a": region["provenance"]["source_url"],
            "provenance_b": iso["source_url"] if correspondance else INCONNU,
        })

    for cle, (code, nom) in sorted(subdivisions.items()):
        if cle in regions:
            continue
        lignes.append({
            "entity": nom, "source_a": INCONNU, "source_b": nom,
            "iso_code_a": INCONNU, "iso_code_b": code,
            "status": ABSENT_DE_A,
            "provenance_a": INCONNU, "provenance_b": iso["source_url"],
        })

    par_statut: Dict[str, int] = {}
    for ligne in lignes:
        par_statut[ligne["status"]] = par_statut.get(ligne["status"], 0) + 1

    return {
        "comparable": True,
        "entity_type": "region",
        "source_a": {
            "name": "geoBoundaries (gbOpen) SEN ADM1",
            "count": len(regions),
            "tier": "TIER_B_INTERNATIONAL",
        },
        "source_b": {
            "name": iso["source"],
            "count": len(subdivisions),
            "tier": iso["source_tier"],
            "version": iso["version"],
            "version_note": iso["version_note"],
        },
        "rows": lignes,
        "by_status": par_statut,
        "resolved": False,
        "note": (
            "Aucun arbitrage. Une liste ISO sans date de version peut être "
            "ancienne ou divergente ; trancher demanderait une source "
            "sénégalaise officielle, injoignable depuis cet environnement."
        ),
    }


def compare_department_count(
    connaissance: Dict[str, Any], expected: int = 46
) -> Dict[str, Any]:
    """
    Confronte le nombre de départements acquis à celui annoncé par la directive.

    Args:
        expected: Le nombre annoncé. Ce n'est **pas** une source : c'est une
            affirmation, et le statut le dit.

    Returns:
        Le comparatif, au statut `UNKNOWN` — pas `CONFLICT`. `CONFLICT`
        supposerait qu'une source B existe et porte 46 ; ici, rien ne la porte.
    """
    mesure = connaissance["counts"]["departments"]
    return {
        "entity": "nombre de départements",
        "source_a": {
            "name": "geoBoundaries (gbOpen) SEN ADM2",
            "value": mesure,
            "tier": "TIER_B_INTERNATIONAL",
            "provenance": connaissance["departments"][0]["provenance"]["source_url"],
        },
        "source_b": {
            "name": "directive du projet (affirmation, pas source)",
            "value": expected,
            "tier": INCONNU,
            "provenance": INCONNU,
        },
        "status": MATCH if mesure == expected else INCONNU,
        "resolved": False,
        "reason": (
            "" if mesure == expected else
            f"{mesure} départements dans la source acquise, {expected} annoncés "
            "par la directive. Le statut est UNKNOWN et non CONFLICT : un "
            "conflit suppose deux sources, et le second chiffre n'en a pas. "
            "Forcer le jeu de données à la valeur attendue aurait été la "
            "fabrication la plus facile de ce chantier, et la plus invisible."
        ),
        "what_would_settle_it": [
            "Le découpage publié par le ministère chargé des collectivités "
            "territoriales, ou l'ANSD (`ansd.sn`)",
            "Ces domaines sont refusés par le mandataire de cet environnement — "
            "voir `python scripts/activate_senegal_sources.py`",
        ],
    }


def discrepancy_report(
    connaissance: Optional[Dict[str, Any]] = None, expected_departments: int = 46
) -> Dict[str, Any]:
    """Assemble le rapport de divergences, régions et départements."""
    from .master_rag import load_all_knowledge

    donnees = connaissance or load_all_knowledge()
    regions = compare_regions(donnees)
    departements = compare_department_count(donnees, expected_departments)

    return {
        "regions": regions,
        "department_count": departements,
        "unresolved": [
            ligne["entity"] for ligne in regions.get("rows", [])
            if ligne["status"] not in (MATCH,)
        ],
        "statuses_used": sorted({
            ligne["status"] for ligne in regions.get("rows", [])
        } | {departements["status"]}),
        "resolved_by_guessing": False,
        "note": (
            "Les divergences sont représentées, pas arbitrées. Une divergence "
            "arbitrée en silence disparaît du rapport et réapparaît dans une "
            "réponse."
        ),
    }


def discrepancy_rows(connaissance: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Retourne les lignes de comparaison, pour un affichage ou un test."""
    return discrepancy_report(connaissance)["regions"].get("rows", [])
