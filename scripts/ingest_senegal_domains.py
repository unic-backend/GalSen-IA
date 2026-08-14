"""
Peupler les domaines sénégalais depuis des sources réellement joignables.

    python scripts/ingest_senegal_domains.py            # acquiert et écrit
    python scripts/ingest_senegal_domains.py --offline  # retraite ce qui est là
    python scripts/ingest_senegal_domains.py --json     # rapport brut

## Pourquoi ces sources et pas les sources sénégalaises

`scripts/activate_senegal_sources.py` mesure que les neuf domaines
institutionnels sénégalais inscrits au registre sont **injoignables depuis cet
environnement** : le mandataire refuse la connexion avant qu'aucune requête ne
parte. Ce n'est pas un refus des sites, et ce n'est pas contournable — l'ADR-021
l'interdit et rien ici ne l'essaie.

La règle du VOLET est alors explicite : *trouver une autre source vérifiée*.
Celles retenues ici sont les seules qui satisfont **trois conditions à la fois** :
joignables, publiques, et rattachables à une institution nommée.

## Ce que ces sources sont exactement — et ce qu'elles ne sont pas

Aucune n'est l'État sénégalais. Ce sont des **redistributions** hébergées sur
GitHub de données produites ailleurs :

| Ce qui est récupéré | Rang de ce qui est récupéré | Institution en amont |
|---|---|---|
| `datasets/gdp` | `TIER_C_SECONDARY` | Banque mondiale (`TIER_B`) |
| `datasets/population` | `TIER_C_SECONDARY` | Banque mondiale (`TIER_B`) |
| `datasets/country-codes` | `TIER_C_SECONDARY` | ISO 3166 / ONU (`TIER_B`) |
| `datasets/airport-codes` | `TIER_C_SECONDARY` | OurAirports (`TIER_C`) |
| `datasets/un-locode` | `TIER_C_SECONDARY` | UN/CEFACT (`TIER_B`) |

**Le rang porté par chaque objet est celui de ce qui a été récupéré**, pas celui
de l'amont. Une redistribution peut diverger de sa source ; la présenter au rang
de l'institution ferait passer une copie pour un original. L'amont est nommé à
côté, dans `upstream_source`, pour qu'on puisse remonter.

## Ce qui reste vide, et pourquoi

Histoire, culture, agriculture, pêche, élevage, mines, tourisme, éducation,
santé, juridique : **aucune source joignable ne les porte**. La FAO, l'UNESCO,
l'OMS, la Banque mondiale en direct et les neuf institutions sénégalaises sont
toutes refusées par le mandataire. Les remplir de mémoire fabriquerait des faits
sur un pays réel — partiel vaut mieux que fabriqué.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.security.trust import TrustLevel, wrap  # noqa: E402

INCONNU = "UNKNOWN"
DOSSIER_BRUT = os.path.join("data", "raw_senegal")
DOSSIER_TRAITE = os.path.join("data", "processed_senegal")
SORTIE = "senegal_domain_knowledge.json"

#: Les jeux de données acquis. `tier` est celui de **ce qui est récupéré** ; il
#: n'hérite jamais du rang de l'institution en amont.
JEUX = {
    "gdp": {
        "url": "https://raw.githubusercontent.com/datasets/gdp/main/data/gdp.csv",
        "file": "datasets-gdp.csv",
        "domain": "ECONOMY",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "Banque mondiale — World Development Indicators (NY.GDP.MKTP.CD)",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution) ; conditions de la Banque mondiale en amont",
        "filter": ("Country Code", "SEN"),
        "unit": "USD courants",
        "entity_field": "Country Name",
    },
    "population": {
        "url": "https://raw.githubusercontent.com/datasets/population/main/data/population.csv",
        "file": "datasets-population.csv",
        "domain": "ECONOMY",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "Banque mondiale — World Development Indicators (SP.POP.TOTL)",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution) ; conditions de la Banque mondiale en amont",
        "filter": ("Country Code", "SEN"),
        "unit": "habitants",
        "entity_field": "Country Name",
    },
    "country_codes": {
        "url": "https://raw.githubusercontent.com/datasets/country-codes/main/data/country-codes.csv",
        "file": "datasets-country-codes.csv",
        "domain": "PUBLIC_INSTITUTIONS",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "ISO 3166 ; Nations unies (M49) ; CLDR",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution)",
        "filter": ("ISO3166-1-Alpha-3", "SEN"),
        "unit": INCONNU,
        "entity_field": "official_name_en",
    },
    "airports": {
        "url": "https://raw.githubusercontent.com/datasets/airport-codes/main/data/airport-codes.csv",
        "file": "datasets-airport-codes.csv",
        "domain": "TRANSPORT",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "OurAirports (base communautaire)",
        "upstream_tier": "TIER_C_SECONDARY",
        "tier": "TIER_C_SECONDARY",
        "licence": "Domaine public (OurAirports)",
        "filter": ("iso_country", "SN"),
        "unit": INCONNU,
        "entity_field": "name",
    },
    "iso_3166_2": {
        "url": "https://raw.githubusercontent.com/olahol/iso-3166-2.json/master/iso-3166-2.json",
        "file": "iso-3166-2.json",
        "domain": "ADMINISTRATION",
        "publisher": "olahol/iso-3166-2.json (redistribution communautaire)",
        "upstream_source": "ISO 3166-2 — subdivisions",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "MIT (redistribution) ; ISO 3166-2 en amont",
        "filter": ("__json_country__", "SN"),
        "unit": INCONNU,
        "entity_field": "name",
    },
    "locode": {
        "url": "https://raw.githubusercontent.com/datasets/un-locode/master/data/code-list.csv",
        "file": "datasets-un-locode.csv",
        "domain": "TRANSPORT",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "UN/CEFACT — UN/LOCODE",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution) ; UN/LOCODE en amont",
        "filter": ("Country", "SN"),
        "unit": INCONNU,
        "entity_field": "Name",
    },
}

#: Domaines que ce script peut peupler. Les autres restent vides : le dire ici
#: évite de laisser croire qu'ils ont été tentés et ont échoué.
DOMAINES_COUVERTS = ("ECONOMY", "PUBLIC_INSTITUTIONS", "TRANSPORT", "ADMINISTRATION")

#: Ce qui empêche les autres domaines d'être peuplés, mesuré et non supposé.
DOMAINES_SANS_SOURCE = {
    "HISTORY": "Aucune source joignable. Les archives et l'UCAD sont refusées par le mandataire.",
    "CULTURE": "Aucune source joignable. L'UNESCO (whc.unesco.org) est refusée par le mandataire.",
    "AGRICULTURE": "Aucune source joignable. La FAO et l'ISRA sont refusées par le mandataire.",
    "FISHERIES": "Aucune source joignable. Les ports UN/LOCODE existent mais ne disent rien de la pêche : les y rattacher serait une inférence.",
    "LIVESTOCK": "Aucune source joignable.",
    "MINING": "Aucune source joignable.",
    "TOURISM": "Aucune source joignable.",
    "EDUCATION": "Aucune source joignable.",
    "HEALTH": "Aucune source joignable. L'OMS et le ministère de la Santé sont refusés par le mandataire.",
    "LEGAL": "Aucune source joignable. Le Journal officiel est refusé par le mandataire.",
}


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _empreinte(donnees: bytes) -> str:
    """Retourne l'empreinte SHA-256 d'un contenu."""
    return hashlib.sha256(donnees).hexdigest()


def _maintenant() -> str:
    """Retourne l'instant courant en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def download(cle: str, dossier: str) -> Dict[str, Any]:
    """
    Récupère un jeu de données et le conserve **tel quel**.

    Le contenu passe par la barrière de confiance : un fichier public reste une
    donnée externe, quelle que soit la réputation de l'hébergeur.
    """
    from src.acquisition.fetcher import FetchRefused, fetch

    jeu = JEUX[cle]
    cible = os.path.join(dossier, jeu["file"])
    depart = time.monotonic()
    try:
        resultat = fetch(
            jeu["url"],
            allowed_content_types=["text", "csv", "binary"],
            rate_limit_rps=3.0,
            max_bytes=128 * 1024 * 1024,
        )
    except (FetchRefused, OSError) as erreur:
        return {
            "key": cle, "url": jeu["url"], "ok": False,
            "error": f"{type(erreur).__name__}: {erreur}",
        }

    enveloppe = wrap(
        resultat.body[:200_000].decode("utf-8", errors="replace"),
        TrustLevel.EXTERNAL, origin=jeu["url"],
    )
    os.makedirs(dossier, exist_ok=True)
    with open(cible, "wb") as fichier:
        fichier.write(resultat.body)

    return {
        "key": cle,
        "url": jeu["url"],
        "path": cible,
        "ok": True,
        "bytes": len(resultat.body),
        "content_hash": _empreinte(resultat.body),
        "retrieval_date": _maintenant(),
        "seconds": round(time.monotonic() - depart, 2),
        "trust_level": enveloppe.level.value,
        "suspicious_patterns": len(enveloppe.suspicions),
    }


def rows_for_senegal(contenu: bytes, cle: str) -> List[Dict[str, str]]:
    """
    Retourne les lignes qui concernent le Sénégal, et elles seules.

    Le filtre porte sur un **code de pays**, jamais sur le nom : « Senegal »
    apparaît aussi dans « Senegal River », et filtrer sur le texte ferait entrer
    des lignes qui parlent d'ailleurs.
    """
    champ, valeur = JEUX[cle]["filter"]
    texte = contenu.decode("utf-8", errors="replace")

    # Un JSON de subdivisions ne se lit pas comme un CSV : le pays y est une
    # clé, pas une colonne.
    if champ == "__json_country__":
        pays = (json.loads(texte).get(valeur) or {}).get("divisions", {})
        return [{"code": code, "name": nom} for code, nom in sorted(pays.items())]

    lecteur = csv.DictReader(io.StringIO(texte))
    return [
        ligne for ligne in lecteur
        if (ligne.get(champ) or "").strip() == valeur
    ]


def _provenance(cle: str, telechargement: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble la provenance d'un objet, avec l'amont **nommé à côté**.

    Le rang est celui de ce qui a été récupéré. Une redistribution peut diverger
    de sa source ; lui donner le rang de l'institution ferait passer une copie
    pour un original.
    """
    jeu = JEUX[cle]
    return {
        "source": f"{jeu['publisher']} — {os.path.basename(jeu['url'])}",
        "source_url": jeu["url"],
        "source_type": "E. SECONDARY DATA (redistribution)",
        "source_tier": jeu["tier"],
        "upstream_source": jeu["upstream_source"],
        "upstream_tier": jeu["upstream_tier"],
        "licence": jeu["licence"],
        "retrieval_date": telechargement.get("retrieval_date", INCONNU),
        "publication_date": INCONNU,
        "content_hash": telechargement.get("content_hash", INCONNU),
        "verification_status": "redistribution_not_verified_against_upstream",
        "confidence": "reported_by_redistribution",
    }


def build_items(cle: str, lignes: List[Dict[str, str]], telechargement: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Construit les objets de connaissance d'un jeu de données.

    Chaque objet porte l'année, l'unité et la source quand elles existent — une
    valeur économique sans année ni unité n'est pas une donnée, c'est un nombre.
    """
    jeu = JEUX[cle]
    provenance = _provenance(cle, telechargement)
    objets = []

    for ligne in lignes:
        if cle in ("gdp", "population"):
            annee = (ligne.get("Year") or "").strip()
            valeur = (ligne.get("Value") or "").strip()
            if not annee or not valeur:
                continue
            objets.append({
                "entity": "Sénégal",
                "type": "gdp_current_usd" if cle == "gdp" else "population_total",
                "value": {"year": annee, "amount": valeur, "unit": jeu["unit"]},
                "year": annee,
                **provenance,
            })
        elif cle == "country_codes":
            objets.append({
                "entity": (ligne.get("official_name_en") or "Senegal").strip(),
                "type": "state_identifiers",
                "value": {
                    "iso_alpha3": (ligne.get("ISO3166-1-Alpha-3") or INCONNU).strip(),
                    "iso_alpha2": (ligne.get("ISO3166-1-Alpha-2") or INCONNU).strip(),
                    "iso_numeric": (ligne.get("ISO3166-1-numeric") or INCONNU).strip(),
                    "dial_code": (ligne.get("Dial") or INCONNU).strip(),
                    "currency": (ligne.get("ISO4217-currency_alphabetic_code") or INCONNU).strip(),
                    "currency_name": (ligne.get("ISO4217-currency_name") or INCONNU).strip(),
                    "capital": (ligne.get("Capital") or INCONNU).strip(),
                    "official_name_fr": (ligne.get("official_name_fr") or INCONNU).strip(),
                    "is_independent": (ligne.get("is_independent") or INCONNU).strip(),
                },
                "year": INCONNU,
                **provenance,
            })
        elif cle == "airports":
            objets.append({
                "entity": (ligne.get("name") or INCONNU).strip(),
                "type": f"airport:{(ligne.get('type') or INCONNU).strip()}",
                "value": {
                    "ident": (ligne.get("ident") or INCONNU).strip(),
                    "iata": (ligne.get("iata_code") or "").strip() or INCONNU,
                    "municipality": (ligne.get("municipality") or "").strip() or INCONNU,
                    "iso_region": (ligne.get("iso_region") or INCONNU).strip(),
                    "coordinates": (ligne.get("coordinates") or INCONNU).strip(),
                },
                "year": INCONNU,
                **provenance,
            })
        elif cle == "iso_3166_2":
            objets.append({
                "entity": ligne["name"],
                "type": "iso_3166_2_subdivision",
                "value": {"code": ligne["code"], "name": ligne["name"]},
                "year": INCONNU,
                **provenance,
            })
        elif cle == "locode":
            objets.append({
                "entity": (ligne.get("Name") or INCONNU).strip(),
                "type": "un_locode_location",
                "value": {
                    "locode": f"SN {(ligne.get('Location') or '').strip()}",
                    "function": (ligne.get("Function") or INCONNU).strip(),
                    "status": (ligne.get("Status") or INCONNU).strip(),
                    "subdivision": (ligne.get("Subdivision") or "").strip() or INCONNU,
                    "coordinates": (ligne.get("Coordinates") or "").strip() or INCONNU,
                },
                "year": INCONNU,
                **provenance,
            })
    return objets


def run(
    dossier_brut: Optional[str] = None,
    dossier_traite: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """Acquiert les jeux joignables, en dérive des objets, et écrit le résultat."""
    racine = _racine()
    brut = dossier_brut or os.path.join(racine, DOSSIER_BRUT)
    traite = dossier_traite or os.path.join(racine, DOSSIER_TRAITE)
    os.makedirs(brut, exist_ok=True)
    os.makedirs(traite, exist_ok=True)

    depart = time.monotonic()
    telechargements, echecs = [], []
    domaines: Dict[str, List[Dict[str, Any]]] = {nom: [] for nom in DOMAINES_COUVERTS}

    for cle, jeu in JEUX.items():
        chemin = os.path.join(brut, jeu["file"])
        if offline or os.path.isfile(chemin):
            if not os.path.isfile(chemin):
                echecs.append({"key": cle, "error": f"Fichier absent : {chemin}"})
                continue
            with open(chemin, "rb") as fichier:
                donnees = fichier.read()
            entree = {
                "key": cle, "url": jeu["url"], "path": chemin, "ok": True,
                "bytes": len(donnees), "content_hash": _empreinte(donnees),
                "retrieval_date": datetime.fromtimestamp(
                    os.path.getmtime(chemin), tz=timezone.utc
                ).isoformat(),
                "from_cache": True,
            }
        else:
            entree = download(cle, brut)
            if not entree["ok"]:
                telechargements.append(entree)
                echecs.append(entree)
                continue
            with open(chemin, "rb") as fichier:
                donnees = fichier.read()

        lignes = rows_for_senegal(donnees, cle)
        entree["senegal_rows"] = len(lignes)
        telechargements.append(entree)
        domaines[jeu["domain"]].extend(build_items(cle, lignes, entree))

    connaissance = {
        "knowledge": "senegal_domain_knowledge",
        "country": "SN",
        "built_at": _maintenant(),
        "domains": {
            nom: {
                "populated": bool(objets),
                "items": objets,
                "count": len(objets),
                "reason": "" if objets else "Aucun objet dérivé des sources acquises.",
            }
            for nom, objets in domaines.items()
        },
        "domains_without_source": dict(DOMAINES_SANS_SOURCE),
        "sources": {
            cle: {
                "url": jeu["url"], "tier": jeu["tier"],
                "upstream_source": jeu["upstream_source"],
                "upstream_tier": jeu["upstream_tier"],
                "licence": jeu["licence"], "domain": jeu["domain"],
            }
            for cle, jeu in JEUX.items()
        },
        "note": (
            "Aucune de ces sources n'est l'État sénégalais. Ce sont des "
            "redistributions publiques ; le rang porté par chaque objet est celui "
            "de ce qui a été récupéré, et l'institution en amont est nommée à côté."
        ),
    }

    sortie = os.path.join(traite, SORTIE)
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(connaissance, fichier, ensure_ascii=False, indent=1)

    total = sum(len(objets) for objets in domaines.values())
    return {
        "ok": bool(total) and not echecs,
        "downloads": telechargements,
        "downloaded": sum(1 for t in telechargements if t.get("ok")),
        "failures": echecs,
        "items": total,
        "by_domain": {nom: len(objets) for nom, objets in domaines.items()},
        "domains_populated": sorted(nom for nom, objets in domaines.items() if objets),
        "domains_without_source": sorted(DOMAINES_SANS_SOURCE),
        "seconds": round(time.monotonic() - depart, 2),
        "output": sortie,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Exécute l'acquisition des domaines et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--offline", action="store_true", help="Ne rien télécharger.")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    arguments = analyseur.parse_args(argv)

    rapport = run(offline=arguments.offline)
    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        return 0 if rapport["ok"] else 1

    print(f"Jeux acquis          : {rapport['downloaded']} / {len(JEUX)}")
    for echec in rapport["failures"]:
        print(f"  [échec] {echec.get('key')} — {echec.get('error')}")
    for telechargement in rapport["downloads"]:
        if telechargement.get("ok"):
            print(f"  {telechargement['key']:15} {telechargement.get('senegal_rows', 0):5} ligne(s) Sénégal")
    print(f"Objets de connaissance : {rapport['items']}")
    print(f"Domaines peuplés     : {', '.join(rapport['domains_populated'])}")
    print(f"Domaines sans source : {len(rapport['domains_without_source'])} — avec leur raison")
    print(f"Temps                : {rapport['seconds']} s")
    print(f"Sortie               : {rapport['output']}")
    return 0 if rapport["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
