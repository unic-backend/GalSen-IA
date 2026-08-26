#!/usr/bin/env python3
"""
Lance un grand modèle sur un serveur GPU — ou dit pourquoi il ne le fera pas.

## Ce que ce script est

Un lecteur de `config/models/*.yaml`. Les commandes qu'il rend ne sont pas
construites ici : elles sont **recopiées** des recettes officielles de vLLM
(`vllm-project/recipes`), lues le 2026-08-24. Un drapeau inventé pour un
déploiement de 400 milliards de paramètres coûte une heure de GPU loué à
découvrir.

## Ce qu'il refuse de faire

Il n'exécute rien sans `--execute`, et il **vérifie le matériel avant**. Lancer
`vllm serve` pour un modèle qui demande huit H200 sur une machine sans GPU
produit une trace de plusieurs centaines de lignes dont la première cause est
noyée ; le refus explicite est plus utile.

    python scripts/models/serve_large.py                  # liste les modèles
    python scripts/models/serve_large.py kimi-k2.5        # montre la commande
    python scripts/models/serve_large.py kimi-k2.5 --execute
"""

import argparse
import glob
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REPERTOIRE = os.path.join(RACINE, "config", "models")


def charger(nom: str) -> Optional[Dict[str, Any]]:
    """
    Lit la configuration d'un modèle.

    Args:
        nom: Nom du modèle, sans extension.

    Returns:
        La configuration, ou `None` si le fichier n'existe pas.
    """
    import yaml

    chemin = os.path.join(REPERTOIRE, f"{nom}.yaml")
    if not os.path.isfile(chemin):
        return None
    with open(chemin, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


def disponibles() -> List[Dict[str, Any]]:
    """Retourne toutes les configurations déclarées, triées par nom."""
    import yaml

    configurations = []
    for chemin in sorted(glob.glob(os.path.join(REPERTOIRE, "*.yaml"))):
        with open(chemin, encoding="utf-8") as fichier:
            configurations.append(yaml.safe_load(fichier))
    return configurations


def gpus_presents() -> Optional[int]:
    """
    Compte les GPU NVIDIA visibles.

    Returns:
        Le nombre de GPU, ou `None` quand `nvidia-smi` est absent — ce qui n'est
        pas « zéro GPU » mais « rien ne permet de le savoir ». Les confondre
        ferait refuser un lancement sur une machine AMD parfaitement capable.
    """
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        sortie = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None
    return len([ligne for ligne in sortie.stdout.splitlines() if ligne.strip()])


def commande_de(configuration: Dict[str, Any], variante: str = "") -> List[str]:
    """
    Retourne la commande de lancement, éventuellement une variante.

    Args:
        configuration: La configuration lue.
        variante: Suffixe de clé, par exemple `low_latency`.

    Returns:
        La commande, argument par argument.
    """
    cle = f"serve_command_{variante}" if variante else "serve_command"
    return [str(a) for a in (configuration.get(cle) or configuration.get("serve_command") or [])]


def _rapport_materiel(configuration: Dict[str, Any]) -> List[str]:
    """Rend ce que le modèle exige et ce que la machine offre."""
    materiel = configuration.get("hardware", {})
    compte = gpus_presents()
    vus = "inconnu (nvidia-smi absent)" if compte is None else str(compte)
    lignes = [
        f"  exigé    : {materiel.get('minimum', 'non déclaré')}",
        f"  GPU vus  : {vus}",
    ]
    if materiel.get("alternative"):
        lignes.insert(1, f"  ou       : {materiel['alternative']}")
    return lignes


def peut_lancer(configuration: Dict[str, Any]) -> tuple:
    """
    Dit si le lancement a une chance d'aboutir sur cette machine.

    Returns:
        Le couple `(possible, motif)`. `possible` est faux dès qu'une raison
        connue s'y oppose ; il n'est jamais vrai « par optimisme ».
    """
    if shutil.which("vllm") is None:
        return False, "vLLM n'est pas installé sur cette machine."
    compte = gpus_presents()
    if compte is None:
        return False, "Aucun GPU NVIDIA détectable (`nvidia-smi` absent)."
    if compte == 0:
        return False, "Aucun GPU NVIDIA visible."

    commande = commande_de(configuration)
    for drapeau in ("--tensor-parallel-size", "-dp"):
        if drapeau in commande:
            exige = int(commande[commande.index(drapeau) + 1])
            if compte < exige:
                return False, f"{exige} GPU exigés par la commande, {compte} vus."
    return True, f"{compte} GPU disponibles."


def montrer(configuration: Dict[str, Any], variante: str = "") -> str:
    """Assemble le rapport d'un modèle."""
    lignes = [
        f"{configuration['display_name']}  ({configuration['name']})",
        f"  état     : {configuration['state']}",
        f"  poids    : {configuration.get('huggingface_id', 'non déclaré')}",
        f"  backend  : {configuration.get('backend', 'vllm')}",
    ]
    lignes += _rapport_materiel(configuration)

    possible, motif = peut_lancer(configuration)
    lignes.append(f"  lançable : {'oui' if possible else 'NON'} — {motif}")

    lignes += ["", "  Commande (recette officielle vLLM, recopiée) :",
               "    " + " \\\n      ".join(commande_de(configuration, variante))]

    roles = configuration.get("roles") or []
    if roles:
        lignes += ["", f"  Rôles visés une fois servi : {', '.join(roles)}"]

    lignes += [
        "",
        "  Une fois le serveur démarré, raccorder la plateforme :",
        "    export GALSEN_OPENAI_COMPATIBLE_URL=http://SERVEUR:8000/v1",
        "    python scripts/models/connect.py",
    ]
    return "\n".join(lignes)


def main() -> int:
    """Point d'entrée. Rend 0 si tout s'est bien passé."""
    analyseur = argparse.ArgumentParser(
        description="Montre ou lance la commande de service d'un grand modèle.",
    )
    analyseur.add_argument("modele", nargs="?", help="Nom du modèle (sans extension)")
    analyseur.add_argument("--variante", default="", help="Par exemple : low_latency")
    analyseur.add_argument(
        "--execute", action="store_true",
        help="Lance réellement la commande ; refusé si le matériel ne suit pas",
    )
    arguments = analyseur.parse_args()

    if not arguments.modele:
        print("Modèles préparés (aucun n'est téléchargé) :\n")
        for configuration in disponibles():
            print(f"  {configuration['name']:16s} {configuration['display_name']:24s} "
                  f"{configuration['state']}")
        print("\n  python scripts/models/serve_large.py <nom>")
        return 0

    configuration = charger(arguments.modele)
    if configuration is None:
        noms = ", ".join(c["name"] for c in disponibles())
        print(f"Aucune configuration « {arguments.modele} ». Connus : {noms}")
        return 1

    print(montrer(configuration, arguments.variante))

    if not arguments.execute:
        return 0

    possible, motif = peut_lancer(configuration)
    if not possible:
        print(f"\nLancement refusé : {motif}")
        print("Rien n'a été exécuté — un échec de vLLM noierait cette cause "
              "dans plusieurs centaines de lignes de trace.")
        return 1

    commande = commande_de(configuration, arguments.variante)
    print(f"\nLancement : {' '.join(commande)}\n")
    return subprocess.call(commande)


if __name__ == "__main__":
    raise SystemExit(main())
