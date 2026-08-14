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


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chemin_brut(nom: str) -> str:
    """Le chemin d'un fichier brut."""
    return os.path.join(_racine(), DOSSIER_BRUT, nom)


def sources_manquantes() -> List[str]:
    """Les fichiers bruts nécessaires qui ne sont pas là."""
    return [
        jeu["file"] for jeu in JEUX_MONDIAUX.values()
        if not os.path.isfile(_chemin_brut(jeu["file"]))
    ]


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


def write(monde: Dict[str, Any]) -> str:
    """
    Écrit la connaissance dérivée.

    Args:
        monde: L'objet construit.

    Returns:
        Le chemin écrit.
    """
    dossier = os.path.join(_racine(), DOSSIER_TRAITE)
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, SORTIE)
    with open(chemin, "w", encoding="utf-8") as flux:
        json.dump(monde, flux, ensure_ascii=False, indent=1, sort_keys=True)
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
    if arguments.json:
        print(json.dumps(monde["counts"], ensure_ascii=False))
        return 0

    comptes = monde["counts"]
    print(f"Connaissance mondiale écrite : {chemin}")
    print(f"  pays dérivés          : {comptes['countries']}")
    print(f"  avec profil complet   : {comptes['with_profile']}")
    print(f"  lignes refusées       : {comptes['refused_rows']}")
    print(f"  désaccords rapportés  : {comptes['disagreements']} (non résolus)")
    print(f"  régions M49           : {len(monde['reference']['regions'])}")
    print("Aucune valeur n'a été écrite de mémoire ; aucune sortie réseau n'a eu lieu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
