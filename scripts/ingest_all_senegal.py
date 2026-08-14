"""
Acquisition et construction de la connaissance sénégalaise.

    python scripts/ingest_all_senegal.py             # télécharge, dérive, écrit
    python scripts/ingest_all_senegal.py --offline   # retraite ce qui est déjà là
    python scripts/ingest_all_senegal.py --json      # rapport brut

## Ce que ce script fait, et ce qu'il refuse de faire

Il **dérive** des entités administratives depuis une source acquise, et il
n'en écrit **aucune de mémoire**. Les 14 régions et les départements du Sénégal
sont lus dans les limites administratives publiées par geoBoundaries, pas dans
la connaissance générale d'un modèle. Un champ qui ne peut pas être établi vaut
`UNKNOWN` — jamais une valeur plausible.

Le rattachement département → région n'est pas non plus déclaré : il est
**calculé** par appartenance géométrique du centroïde du département au polygone
de la région. C'est une dérivation, vérifiable et reproductible ; un
rattachement écrit à la main serait une affirmation.

## Les cinq niveaux de source

Le registre existant (`corpus/sources/senegal.yaml`, ADR-021) porte déjà les
rangs `TIER_A_PRIMARY_OFFICIAL` à `TIER_D_DISCOVERY_ONLY`. Ce script les
réutilise : geoBoundaries est une **source internationale** (`TIER_B`), pas une
source officielle sénégalaise. La distinction voyage jusqu'à chaque objet de
connaissance.

## Ce qui reste vide

Quatorze des seize domaines demandés restent vides, **avec leur raison**. Les
remplir demanderait des documents que ce script n'acquiert pas, et les remplir
de mémoire serait exactement ce que ce dépôt refuse : partiel vaut mieux que
fabriqué.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.security.trust import TrustLevel, wrap  # noqa: E402

#: Valeur d'un champ que personne n'a pu établir.
INCONNU = "UNKNOWN"

#: Les sources acquises. Le contenu réel des fichiers geoBoundaries est servi
#: par Git LFS : `raw.githubusercontent.com` ne rend que le pointeur, et
#: `media.githubusercontent.com` rend le fichier. L'URL de la directive pointait
#: vers un nom de fichier qui n'existe plus (`…_gbOpen.geojson`) — corrigée ici,
#: et la correction est tracée dans la provenance de chaque objet.
SOURCES = {
    "ADM1": {
        "url": (
            "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/"
            "releaseData/gbOpen/SEN/ADM1/geoBoundaries-SEN-ADM1.geojson"
        ),
        "file": "geoBoundaries-SEN-ADM1.geojson",
        "level": "region",
    },
    "ADM2": {
        "url": (
            "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/"
            "releaseData/gbOpen/SEN/ADM2/geoBoundaries-SEN-ADM2.geojson"
        ),
        "file": "geoBoundaries-SEN-ADM2.geojson",
        "level": "department",
    },
}

#: Ce qu'est geoBoundaries : une source internationale ouverte, pas l'État.
SOURCE_NOM = "geoBoundaries (gbOpen)"
SOURCE_TYPE = "D. INTERNATIONAL DATA"
SOURCE_TIER = "TIER_B_INTERNATIONAL"
SOURCE_LICENCE = "Open Data Commons Open Database License (ODbL) — voir geoboundaries.org"

DOSSIER_BRUT = os.path.join("data", "raw_senegal")
DOSSIER_TRAITE = os.path.join("data", "processed_senegal")
SORTIE = "senegal_master_knowledge.json"

#: Les seize domaines demandés. Chacun est déclaré, peuplé ou non — un domaine
#: absent de la liste serait indistinguable d'un domaine oublié.
DOMAINES = (
    "GEOGRAPHY", "ADMINISTRATION", "AGRICULTURE", "FISHERIES", "LIVESTOCK",
    "MINING", "TOURISM", "TRANSPORT", "EDUCATION", "HEALTH", "ECONOMY",
    "CULTURE", "HISTORY", "LANGUAGES", "PUBLIC_INSTITUTIONS", "LEGAL",
)

#: Pourquoi un domaine reste vide. Écrit une fois, pour tous : le remplir
#: demanderait des documents qu'aucune source acquise ici ne porte.
VIDE = (
    "Aucune source acquise ne porte ce domaine. Le remplir demanderait des "
    "documents déclarés dans le registre (ADR-021) et approuvés ; l'écrire de "
    "mémoire fabriquerait des faits sur un pays réel."
)


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _empreinte(donnees: bytes) -> str:
    """Retourne l'empreinte SHA-256 d'un contenu."""
    return hashlib.sha256(donnees).hexdigest()


def _maintenant() -> str:
    """Retourne l'instant courant en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Acquisition
# ----------------------------------------------------------------------

def download(cle: str, dossier: str) -> Dict[str, Any]:
    """
    Récupère une source et la conserve **telle quelle**.

    Le fichier brut n'est jamais modifié : la couche brute est immuable, et
    c'est ce qui rend le traitement reproductible et vérifiable.
    """
    from src.acquisition.fetcher import FetchRefused, fetch

    source = SOURCES[cle]
    cible = os.path.join(dossier, source["file"])
    depart = time.monotonic()
    try:
        resultat = fetch(
            source["url"],
            # Git LFS sert en `application/octet-stream` : le type est déclaré
            # ici, pour cette source, pas ouvert globalement.
            allowed_content_types=["json", "geojson", "binary", "text"],
            rate_limit_rps=2.0,
            max_bytes=128 * 1024 * 1024,
        )
    except (FetchRefused, OSError) as erreur:
        return {
            "key": cle, "url": source["url"], "ok": False,
            "error": f"{type(erreur).__name__}: {erreur}",
        }

    # Une donnée externe reste une donnée externe, quelle que soit la
    # réputation de l'hébergeur.
    enveloppe = wrap(
        resultat.body[:200_000].decode("utf-8", errors="replace"),
        TrustLevel.EXTERNAL, origin=source["url"],
    )
    os.makedirs(dossier, exist_ok=True)
    with open(cible, "wb") as fichier:
        fichier.write(resultat.body)

    return {
        "key": cle,
        "url": source["url"],
        "path": cible,
        "ok": True,
        "bytes": len(resultat.body),
        "content_hash": _empreinte(resultat.body),
        "retrieval_date": _maintenant(),
        "seconds": round(time.monotonic() - depart, 2),
        "trust_level": enveloppe.level.value,
        "suspicious_patterns": len(enveloppe.suspicions),
    }


def validate_geojson(donnees: bytes) -> Dict[str, Any]:
    """
    Valide qu'un contenu est un GeoJSON exploitable.

    Un fichier invalide est **dit invalide** ; le traiter quand même produirait
    des entités partielles qui ressembleraient à des entités.
    """
    try:
        objet = json.loads(donnees.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        return {"valid": False, "reason": f"JSON illisible : {erreur}", "features": 0}

    if not isinstance(objet, dict) or objet.get("type") != "FeatureCollection":
        return {
            "valid": False,
            "reason": f"Type « {objet.get('type') if isinstance(objet, dict) else '?'} » : "
                      "un GeoJSON de limites administratives est une FeatureCollection.",
            "features": 0,
        }

    traits = objet.get("features")
    if not isinstance(traits, list) or not traits:
        return {"valid": False, "reason": "Aucune entité dans la collection.", "features": 0}

    sans_geometrie = [
        index for index, trait in enumerate(traits)
        if not isinstance(trait.get("geometry"), dict)
        or trait["geometry"].get("type") not in ("Polygon", "MultiPolygon")
    ]
    return {
        "valid": not sans_geometrie,
        "reason": (
            "" if not sans_geometrie else
            f"{len(sans_geometrie)} entité(s) sans polygone exploitable."
        ),
        "features": len(traits),
        "object": objet,
    }


# ----------------------------------------------------------------------
# Géométrie — dérivation, pas déclaration
# ----------------------------------------------------------------------

def _anneaux(geometrie: Dict[str, Any]) -> List[List[List[float]]]:
    """Retourne les anneaux extérieurs d'un polygone ou multipolygone."""
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"][0]]
    return [polygone[0] for polygone in geometrie["coordinates"] if polygone]


def bounding_box(geometrie: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Retourne l'emprise `(ouest, sud, est, nord)` d'une géométrie."""
    xs, ys = [], []
    for anneau in _anneaux(geometrie):
        for x, y in anneau:
            xs.append(x)
            ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


def centroid(geometrie: Dict[str, Any]) -> Tuple[float, float]:
    """
    Retourne le centroïde surfacique de la plus grande composante.

    La plus grande, et non la moyenne des sommets : une région à îles verrait
    son centre tiré au large, et le rattachement calculé dessus serait faux.
    """
    meilleur, aire_max = None, -1.0
    for anneau in _anneaux(geometrie):
        aire = cx = cy = 0.0
        for index in range(len(anneau) - 1):
            x0, y0 = anneau[index]
            x1, y1 = anneau[index + 1]
            croix = x0 * y1 - x1 * y0
            aire += croix
            cx += (x0 + x1) * croix
            cy += (y0 + y1) * croix
        if abs(aire) < 1e-12:
            continue
        aire *= 0.5
        centre = (cx / (6 * aire), cy / (6 * aire))
        if abs(aire) > aire_max:
            meilleur, aire_max = centre, abs(aire)

    if meilleur is None:  # géométrie dégénérée : moyenne des sommets
        points = [point for anneau in _anneaux(geometrie) for point in anneau]
        return (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
        )
    return meilleur


def point_in_ring(point: Tuple[float, float], anneau: List[List[float]]) -> bool:
    """Indique si un point est dans un anneau, par lancer de rayon."""
    x, y = point
    dedans = False
    for index in range(len(anneau) - 1):
        x0, y0 = anneau[index]
        x1, y1 = anneau[index + 1]
        if (y0 > y) != (y1 > y):
            coupe = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if coupe > x:
                dedans = not dedans
    return dedans


def point_in_geometry(point: Tuple[float, float], geometrie: Dict[str, Any]) -> bool:
    """Indique si un point est dans une géométrie (anneaux extérieurs)."""
    return any(point_in_ring(point, anneau) for anneau in _anneaux(geometrie))


def _distance2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Retourne le carré de la distance entre deux points."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def attach_departments(
    regions: List[Dict[str, Any]], departements: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Rattache chaque département à sa région, **par calcul**.

    Le centroïde du département est cherché dans les polygones de région. Aucun
    rattachement n'est écrit à la main : ce serait une affirmation, pas une
    dérivation.

    Un département dont le centroïde ne tombe dans aucune région reçoit la
    région **la plus proche**, et le rapport le dit : c'est une approximation
    assumée, pas un fait. Sans elle, un département côtier au centroïde en mer
    resterait orphelin.
    """
    rattachements, approximatifs = {}, []
    for departement in departements:
        centre = departement["centroid"]
        trouvee = next(
            (region for region in regions
             if point_in_geometry(centre, region["_geometry"])),
            None,
        )
        if trouvee is None:
            trouvee = min(regions, key=lambda r: _distance2(centre, r["centroid"]))
            approximatifs.append({
                "department": departement["name"],
                "region": trouvee["name"],
                "method": "plus proche centroïde de région",
            })
        rattachements[departement["shape_id"]] = trouvee["shape_id"]
    return {"parents": rattachements, "approximated": approximatifs}


# ----------------------------------------------------------------------
# Objets de connaissance
# ----------------------------------------------------------------------

def _entites(objet: Dict[str, Any], niveau: str, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Construit les entités d'un niveau administratif depuis un GeoJSON validé."""
    entites = []
    for trait in objet["features"]:
        proprietes = trait.get("properties") or {}
        geometrie = trait["geometry"]
        nom = str(proprietes.get("shapeName") or "").strip()
        if not nom:
            continue
        ouest, sud, est, nord = bounding_box(geometrie)
        entites.append({
            "name": nom,
            "type": niveau,
            "shape_id": str(proprietes.get("shapeID") or INCONNU),
            "iso_code": str(proprietes.get("shapeISO") or "").strip() or INCONNU,
            "centroid": centroid(geometrie),
            "bbox": [ouest, sud, est, nord],
            # Ce que geoBoundaries ne porte pas. Le déduire d'un centroïde ou
            # d'un nom serait une invention : un chef-lieu est une décision
            # administrative, pas une propriété géométrique.
            "chief_lieu": INCONNU,
            "population": INCONNU,
            "area_km2": INCONNU,
            "parent": INCONNU,
            "children": [],
            "provenance": _provenance(source),
            "_geometry": geometrie,
        })
    return entites


def _provenance(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble la provenance d'un objet, au format du dépôt.

    Elle porte ce qui permet de rouvrir la source **et** ce qui dit à quel point
    elle fait autorité : geoBoundaries est international, pas sénégalais
    officiel, et confondre les deux serait la première erreur possible ici.
    """
    return {
        "source": SOURCE_NOM,
        "source_url": source["url"],
        "source_type": SOURCE_TYPE,
        "source_tier": SOURCE_TIER,
        "licence": SOURCE_LICENCE,
        "retrieval_date": source.get("retrieval_date", INCONNU),
        # geoBoundaries ne publie pas de date de publication par fichier dans le
        # GeoJSON lui-même : elle reste inconnue plutôt que confondue avec la
        # date de récupération.
        "publication_date": INCONNU,
        "content_hash": source.get("content_hash", INCONNU),
        "verification_status": "derived_from_source",
        "confidence": "derived",
    }


def build_knowledge(
    fichiers: Dict[str, Dict[str, Any]], wolof: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Construit l'objet de connaissance complet depuis les sources validées.

    Returns:
        Les seize domaines, dont deux peuplés depuis les données acquises et un
        troisième renvoyant au corpus wolof existant. Les treize autres sont
        **déclarés vides avec leur raison** : un domaine absent serait
        indistinguable d'un domaine oublié.
    """
    regions = _entites(fichiers["ADM1"]["object"], "region", fichiers["ADM1"])
    departements = _entites(fichiers["ADM2"]["object"], "department", fichiers["ADM2"])

    liens = attach_departments(regions, departements)
    par_identifiant = {region["shape_id"]: region for region in regions}
    for departement in departements:
        parent = par_identifiant.get(liens["parents"].get(departement["shape_id"], ""))
        if parent is not None:
            departement["parent"] = parent["name"]
            parent["children"].append(departement["name"])

    for entite in regions + departements:
        entite.pop("_geometry", None)
        entite["children"] = sorted(entite["children"])

    domaines = {nom: {"populated": False, "items": [], "reason": VIDE} for nom in DOMAINES}
    domaines["GEOGRAPHY"] = {
        "populated": True,
        "items": [
            {
                "entity": entite["name"],
                "type": entite["type"],
                "value": {
                    "centroid": entite["centroid"],
                    "bbox": entite["bbox"],
                    "iso_code": entite["iso_code"],
                },
                **entite["provenance"],
            }
            for entite in regions + departements
        ],
        "reason": "",
    }
    domaines["ADMINISTRATION"] = {
        "populated": True,
        "items": [
            {
                "entity": entite["name"],
                "type": entite["type"],
                "value": {
                    "parent": entite["parent"],
                    "children": entite["children"],
                    "chief_lieu": entite["chief_lieu"],
                },
                **entite["provenance"],
            }
            for entite in regions + departements
        ],
        "reason": "",
    }
    if wolof:
        domaines["LANGUAGES"] = {
            "populated": True,
            "items": [{
                "entity": "wolof",
                "type": "language_corpus",
                "value": {
                    "records": wolof.get("documents", 0),
                    "standard": wolof.get("normalization_standard", INCONNU),
                    "corpus": wolof.get("source", INCONNU),
                },
                "source": wolof.get("source", INCONNU),
                "source_url": "https://github.com/UniversalDependencies/UD_Wolof-WTB",
                "source_type": "B. ACADEMIC DATA",
                "source_tier": "TIER_A_ACADEMIC",
                "licence": wolof.get("licence", INCONNU),
                "retrieval_date": INCONNU,
                "publication_date": INCONNU,
                "content_hash": INCONNU,
                "verification_status": "reused_existing_artifact",
                "confidence": "derived",
            }],
            "reason": "",
        }

    return {
        "knowledge": "senegal_master_knowledge",
        "country": "SN",
        "built_at": _maintenant(),
        "regions": regions,
        "departments": departements,
        "counts": {
            "regions": len(regions),
            "departments": len(departements),
            "departments_attached": sum(
                1 for d in departements if d["parent"] != INCONNU
            ),
            "attachments_approximated": len(liens["approximated"]),
        },
        "approximated_attachments": liens["approximated"],
        "domains": domaines,
        "unknown_fields": ["chief_lieu", "population", "area_km2", "publication_date"],
        "note": (
            "Les entités sont **dérivées** d'une source acquise, jamais écrites de "
            "mémoire. Un champ que la source ne porte pas vaut UNKNOWN : un "
            "chef-lieu est une décision administrative, pas une propriété "
            "géométrique, et le déduire serait une invention."
        ),
    }


# ----------------------------------------------------------------------
# Exécution
# ----------------------------------------------------------------------

def run(
    dossier_brut: Optional[str] = None,
    dossier_traite: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """Acquiert, valide, dérive et écrit. Rend le rapport complet."""
    racine = _racine()
    brut = dossier_brut or os.path.join(racine, DOSSIER_BRUT)
    traite = dossier_traite or os.path.join(racine, DOSSIER_TRAITE)
    os.makedirs(brut, exist_ok=True)
    os.makedirs(traite, exist_ok=True)

    depart = time.monotonic()
    telechargements, fichiers, echecs = [], {}, []

    for cle, source in SOURCES.items():
        chemin = os.path.join(brut, source["file"])
        if offline or os.path.isfile(chemin):
            if not os.path.isfile(chemin):
                echecs.append({"key": cle, "error": f"Fichier absent : {chemin}"})
                continue
            with open(chemin, "rb") as fichier:
                donnees = fichier.read()
            entree = {
                "key": cle, "url": source["url"], "path": chemin, "ok": True,
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

        telechargements.append(entree)
        validation = validate_geojson(donnees)
        entree["valid_geojson"] = validation["valid"]
        entree["features"] = validation["features"]
        if not validation["valid"]:
            echecs.append({"key": cle, "error": validation["reason"]})
            continue
        fichiers[cle] = {**entree, "object": validation["object"]}

    if set(fichiers) != set(SOURCES):
        return {
            "ok": False,
            "downloads": telechargements,
            "failures": echecs,
            "reason": "Sources manquantes ou invalides : aucune connaissance n'est écrite.",
        }

    wolof = _corpus_wolof()
    temps_acquisition = round(time.monotonic() - depart, 2)

    depart_traitement = time.monotonic()
    connaissance = build_knowledge(fichiers, wolof)
    temps_traitement = round(time.monotonic() - depart_traitement, 2)

    sortie = os.path.join(traite, SORTIE)
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(connaissance, fichier, ensure_ascii=False, indent=1)

    return {
        "ok": True,
        "downloads": telechargements,
        "downloaded": sum(1 for t in telechargements if t.get("ok")),
        "failures": echecs,
        "counts": connaissance["counts"],
        "domains_populated": sorted(
            nom for nom, domaine in connaissance["domains"].items() if domaine["populated"]
        ),
        "domains_empty": sorted(
            nom for nom, domaine in connaissance["domains"].items()
            if not domaine["populated"]
        ),
        "wolof": {"reused": bool(wolof), "records": (wolof or {}).get("documents", 0)},
        "timing": {
            "acquisition_seconds": temps_acquisition,
            "processing_seconds": temps_traitement,
        },
        "output": sortie,
    }


def _corpus_wolof() -> Optional[Dict[str, Any]]:
    """
    Réutilise le corpus wolof déjà construit, sans le reconstruire.

    Un second corpus wolof serait un second corpus wolof : deux vérités, deux
    versions de normalisation, et aucune façon de dire laquelle a servi.
    """
    from src.services.wolof.rag_loader import corpus_report

    rapport = corpus_report()
    return rapport if rapport.get("available") else None


def main(argv: Optional[List[str]] = None) -> int:
    """Exécute l'acquisition et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--offline", action="store_true", help="Ne rien télécharger.")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    arguments = analyseur.parse_args(argv)

    rapport = run(offline=arguments.offline)

    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        return 0 if rapport["ok"] else 1

    if not rapport["ok"]:
        print(f"[arrêt] {rapport['reason']}")
        for echec in rapport["failures"]:
            print(f"  {echec.get('key')} — {echec.get('error')}")
        return 1

    comptes = rapport["counts"]
    print(f"Sources acquises     : {rapport['downloaded']} / {len(SOURCES)}")
    print(f"Régions              : {comptes['regions']}")
    print(f"Départements         : {comptes['departments']} "
          f"({comptes['departments_attached']} rattachés, "
          f"{comptes['attachments_approximated']} par approximation)")
    print(f"Domaines peuplés     : {', '.join(rapport['domains_populated'])}")
    print(f"Domaines vides       : {len(rapport['domains_empty'])} — avec leur raison")
    print(f"Corpus wolof réutilisé : {rapport['wolof']['records']} enregistrements")
    print(f"Temps                : acquisition {rapport['timing']['acquisition_seconds']} s, "
          f"traitement {rapport['timing']['processing_seconds']} s")
    print(f"Sortie               : {rapport['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
