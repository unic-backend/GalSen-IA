"""
Construction de la connaissance mondiale, depuis les jeux déjà acquis.

    python scripts/build_world_knowledge.py          # dérive et écrit
    python scripts/build_world_knowledge.py --json   # rapport brut

## Ce que ce script fait, et ce qu'il refuse de faire

Il **dérive**, il n'acquiert pas. Les deux jeux qu'il lit ont été téléchargés par
`scripts/ingest_senegal_domains.py` et sont **mondiaux** : seul le nom de leur
dossier dit « Sénégal », parce qu'ils ont été acquis pour lui. Aucune sortie
réseau n'est faite ici.

Il n'écrit **aucune valeur de mémoire**. Un champ que la source ne porte pas vaut
`UNKNOWN`. Deux sources qui divergent sont rapportées côte à côte, jamais
réconciliées : choisir en silence rendrait la plateforme catégorique sur ce
qu'elle ne peut pas établir.

La règle de portée est tenue par `src/knowledge_engine/world.py` : **`global` porte
la taxonomie, pas les pays.** Un fait sur la France porte la portée `country:fr`.

## Reproductibilité

Les fichiers bruts ne sont pas versionnés (`data/` est ignoré) ; la connaissance
dérivée l'est, comme pour le Sénégal. Sans les fichiers bruts, ce script s'arrête
en disant lesquels manquent — il ne produit pas un monde vide.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.knowledge_engine.series import (  # noqa: E402
    SERIES_MONDIALES,
    build_series,
    known_country_codes,
)
from src.knowledge_engine.world import (  # noqa: E402
    JEUX_MONDIAUX,
    build_world_knowledge,
)

#: Là où les jeux bruts se trouvent. Le nom dit « Sénégal » ; le contenu est
#: mondial. Les déplacer casserait les scripts sénégalais pour un gain nul.
DOSSIER_BRUT = os.path.join("data", "raw_senegal")

#: Là où la connaissance dérivée est écrite. Versionnée, elle.
DOSSIER_TRAITE = os.path.join("data", "processed_global")

SORTIE = "world_countries.json"

#: Les séries mesurées (phase 52.3), écrites à côté des pays. Séparées : une
#: question sur une capitale n'a pas à charger soixante-cinq ans de population.
SORTIE_SERIES = "world_series.json"


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chemin_brut(nom: str) -> str:
    """Le chemin d'un fichier brut."""
    return os.path.join(_racine(), DOSSIER_BRUT, nom)


def sources_manquantes() -> List[str]:
    """Les fichiers bruts nécessaires qui ne sont pas là."""
    attendus = [jeu["file"] for jeu in JEUX_MONDIAUX.values()]
    attendus += [serie["file"] for serie in SERIES_MONDIALES.values()]
    return [nom for nom in attendus if not os.path.isfile(_chemin_brut(nom))]


def build() -> Dict[str, Any]:
    """
    Construit la connaissance mondiale depuis les fichiers présents.

    Returns:
        L'objet de connaissance, horodaté.

    Raises:
        FileNotFoundError: Si un jeu manque. Le nommer vaut mieux que rendre un
            monde vide.
    """
    manquants = sources_manquantes()
    if manquants:
        raise FileNotFoundError(
            "Jeux bruts absents : " + ", ".join(manquants) + ". Ils sont "
            "reproductibles par `python scripts/ingest_senegal_domains.py`. "
            "Sans eux, ce script ne produit rien plutôt qu'un monde vide."
        )

    with open(_chemin_brut(JEUX_MONDIAUX["country_codes"]["file"]),
              "r", encoding="utf-8") as flux:
        codes = flux.read()
    with open(_chemin_brut(JEUX_MONDIAUX["country_profile"]["file"]),
              "r", encoding="utf-8") as flux:
        profils = json.load(flux)

    monde = build_world_knowledge(codes, profils)
    monde["built_at"] = datetime.now(timezone.utc).isoformat()
    return monde


def build_measured_series(monde: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit les séries mesurées depuis les CSV acquis.

    Args:
        monde: La connaissance mondiale, qui fournit les codes ISO — c'est elle
            qui permet de distinguer un pays d'un agrégat sans liste écrite à la
            main, laquelle vieillirait sans que rien ne le dise.

    Returns:
        Les séries, horodatées.
    """
    contenus = {}
    for cle, serie in SERIES_MONDIALES.items():
        with open(_chemin_brut(serie["file"]), "r", encoding="utf-8") as flux:
            contenus[cle] = flux.read()

    series = build_series(contenus, known_country_codes(monde))
    series["built_at"] = datetime.now(timezone.utc).isoformat()
    return series


def write(objet: Dict[str, Any], nom: str = SORTIE) -> str:
    """
    Écrit une connaissance dérivée.

    Args:
        objet: L'objet construit.
        nom: Le nom du fichier.

    Returns:
        Le chemin écrit.
    """
    dossier = os.path.join(_racine(), DOSSIER_TRAITE)
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom)
    with open(chemin, "w", encoding="utf-8") as flux:
        json.dump(objet, flux, ensure_ascii=False, indent=1, sort_keys=True)
    return chemin


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true",
                           help="Rapport brut, sans texte")
    arguments = analyseur.parse_args(argv)

    try:
        monde = build()
    except (FileNotFoundError, ValueError) as erreur:
        print(f"Arrêt : {erreur}", file=sys.stderr)
        return 1

    chemin = write(monde)
    series = build_measured_series(monde)
    chemin_series = write(series, SORTIE_SERIES)
    if arguments.json:
        print(json.dumps({
            "countries": monde["counts"],
            "series": {cle: valeur["counts"] for cle, valeur in series["series"].items()},
        }, ensure_ascii=False))
        return 0

    comptes = monde["counts"]
    print(f"Connaissance mondiale écrite : {chemin}")
    print(f"  pays dérivés          : {comptes['countries']}")
    print(f"  avec profil complet   : {comptes['with_profile']}")
    print(f"  lignes refusées       : {comptes['refused_rows']}")
    print(f"  désaccords rapportés  : {comptes['disagreements']} (non résolus)")
    print(f"  régions M49           : {len(monde['reference']['regions'])}")
    print(f"Séries mesurées écrites : {chemin_series}")
    for cle, valeur in series["series"].items():
        comptes_serie = valeur["counts"]
        print(f"  {cle:<12} : {comptes_serie['countries']} pays, "
              f"{comptes_serie['aggregates']} agrégats séparés, "
              f"{comptes_serie['refused_rows']} lignes refusées")
    print("Aucune valeur n'a été écrite de mémoire ; aucune sortie réseau n'a eu lieu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
