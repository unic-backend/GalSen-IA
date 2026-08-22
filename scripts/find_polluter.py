#!/usr/bin/env python3
"""
Trouve quel test en casse un autre (candidat C6 de l'audit Superpowers).

## Le problème que ça résout

Un test passe seul et échoue dans la suite. La cause est un *autre* test qui a
laissé quelque chose derrière lui — une variable d'environnement, un singleton,
un fichier, un `sys.modules` modifié. Ce dépôt a déjà corrigé deux défauts de ce
type **à la main** (VOLET 16), et une suite de 7 000 tests en produira d'autres.

Chercher à la main coûte une après-midi. Ce script coûte quelques minutes.

## Deux modes, parce que la source n'en avait qu'un

`find-polluter.sh` d'`obra/superpowers` ne détecte que la **pollution de disque**
— un fichier qui apparaît. C'est utile, mais ce n'est pas le mode d'échec que
pytest produit le plus souvent : ici, ce qui casse un test est presque toujours
un **état en mémoire**.

- `--fails` : le test cible échoue après un autre. C'est le mode principal.
- `--artifact` : un chemin apparaît pendant la suite. C'est le mode d'origine.

## Ce que la source annonçait et ne faisait pas

Son en-tête dit « Bisection script ». Son corps fait un balayage **linéaire** :
il lance chaque fichier de test l'un après l'autre. Sur 333 fichiers, la
différence entre linéaire et dichotomique est réelle — d'où `--bisect`, activé
par défaut dans le mode `--fails`, qui trouve le coupable en ~log2(n)
exécutions au lieu de n.

Le balayage linéaire reste disponible (`--linear`) : quand plusieurs tests
polluent, la dichotomie n'en désigne qu'un, et l'ordre linéaire les montre tous.

---

Origine : `skills/systematic-debugging/find-polluter.sh` de `obra/superpowers`
à `b36e0829` (MIT, Copyright (c) 2025 Jesse Vincent). Adopté comme candidat C6
de `docs/research/superpowers-audit.md`. Réécrit pour pytest ; le mode `--fails`
et la dichotomie n'existent pas dans la source.

MIT License — le texte complet est dans le dépôt d'origine :
https://github.com/obra/superpowers/blob/b36e0829/LICENSE
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

#: Dossiers dont les fichiers ne sont jamais des candidats pollueurs.
IGNORES = {"__pycache__", ".pytest_cache", ".git"}


def collect_test_files(root: Path, pattern: str) -> List[str]:
    """
    Liste les fichiers de test candidats, triés.

    Args:
        root: Racine du dépôt.
        pattern: Motif glob, relatif à la racine.

    Returns:
        Les chemins relatifs, triés — l'ordre est celui dans lequel pytest les
        collecte, donc celui dans lequel une pollution se propage.
    """
    fichiers = [
        str(chemin.relative_to(root))
        for chemin in sorted(root.glob(pattern))
        if chemin.is_file() and not (IGNORES & set(chemin.parts))
    ]
    return fichiers


def _run(args: Sequence[str], root: Path, timeout: int) -> int:
    """Lance pytest et rend son code de sortie ; un dépassement vaut un échec."""
    try:
        acheve = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", *args],
            cwd=str(root), capture_output=True, text=True, timeout=timeout,
        )
        return acheve.returncode
    except subprocess.TimeoutExpired:
        # Un test qui pend est un résultat, pas une panne du script.
        return 124


def target_passes_alone(target: str, root: Path, timeout: int) -> bool:
    """
    Vérifie la prémisse avant de chercher quoi que ce soit.

    Si la cible échoue **seule**, il n'y a pas de pollueur à trouver : le défaut
    est dans la cible. Chercher quand même ferait accuser un innocent.
    """
    return _run([target], root, timeout) == 0


def reproduces(candidates: Sequence[str], target: str, root: Path,
               timeout: int) -> bool:
    """Vrai si la cible échoue quand ces candidats tournent avant elle."""
    return _run([*candidates, target], root, timeout) != 0


def bisect(candidates: List[str], target: str, root: Path,
           timeout: int, verbose: bool) -> Optional[str]:
    """
    Réduit l'ensemble par dichotomie jusqu'à un seul coupable.

    Args:
        candidates: Les fichiers qui tournent avant la cible.
        target: Le test qui échoue.

    Returns:
        Le fichier pollueur, ou `None` si l'échec ne se reproduit pas — auquel
        cas la pollution vient d'ailleurs (ordre interne, parallélisme, état
        externe), et **le dire est plus utile que de désigner un fichier au
        hasard**.
    """
    if not reproduces(candidates, target, root, timeout):
        return None

    restant = list(candidates)
    while len(restant) > 1:
        milieu = len(restant) // 2
        gauche, droite = restant[:milieu], restant[milieu:]
        if verbose:
            print(f"  dichotomie : {len(restant)} → essai de {len(gauche)}",
                  file=sys.stderr)
        if reproduces(gauche, target, root, timeout):
            restant = gauche
        elif reproduces(droite, target, root, timeout):
            restant = droite
        else:
            # Aucune moitié ne reproduit seule : il faut les deux. Un seul
            # fichier ne suffit pas à expliquer l'échec, et l'annoncer serait
            # faux.
            print("Deux fichiers au moins sont nécessaires ensemble ; "
                  "la dichotomie ne peut pas en isoler un.", file=sys.stderr)
            return None
    return restant[0] if restant else None


def linear(candidates: List[str], target: str, root: Path,
           timeout: int, verbose: bool) -> List[str]:
    """Essaie chaque candidat seul avant la cible. Rend **tous** les coupables."""
    coupables = []
    for index, candidat in enumerate(candidates, start=1):
        if verbose:
            print(f"  [{index}/{len(candidates)}] {candidat}", file=sys.stderr)
        if reproduces([candidat], target, root, timeout):
            coupables.append(candidat)
    return coupables


def find_artifact_creator(candidates: List[str], artifact: Path, root: Path,
                          timeout: int, verbose: bool) -> Optional[str]:
    """
    Mode d'origine : quel test fait apparaître ce chemin.

    Returns:
        Le premier fichier après lequel le chemin existe, ou `None`.

    Raises:
        SystemExit: Si le chemin existe **déjà** avant de commencer. Le script
            de départ se contentait de sauter les tests dans ce cas et
            continuait, ce qui rend chaque résultat suivant faux.
    """
    if artifact.exists():
        raise SystemExit(
            f"« {artifact} » existe déjà avant le premier test. Supprimez-le, "
            "sinon la recherche ne peut rien conclure."
        )

    for index, candidat in enumerate(candidates, start=1):
        if verbose:
            print(f"  [{index}/{len(candidates)}] {candidat}", file=sys.stderr)
        _run([candidat], root, timeout)
        if artifact.exists():
            return candidat
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Point d'entrée."""
    analyseur = argparse.ArgumentParser(
        description="Trouve quel test en casse un autre.",
        epilog="Exemples :\n"
               "  scripts/find_polluter.py --fails tests/test_api_health.py\n"
               "  scripts/find_polluter.py --artifact galsen.sqlite\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyseur.add_argument("--fails", metavar="TEST",
                           help="Le test qui échoue dans la suite et passe seul")
    analyseur.add_argument("--artifact", metavar="CHEMIN",
                           help="Un chemin qui apparaît pendant la suite")
    analyseur.add_argument("--pattern", default="tests/**/test_*.py",
                           help="Motif des candidats (défaut : %(default)s)")
    analyseur.add_argument("--linear", action="store_true",
                           help="Balayage linéaire : trouve TOUS les pollueurs")
    analyseur.add_argument("--timeout", type=int, default=900,
                           help="Secondes par exécution (défaut : %(default)s)")
    analyseur.add_argument("--root", default=".", help="Racine du dépôt")
    analyseur.add_argument("-q", "--quiet", action="store_true")
    options = analyseur.parse_args(argv)

    if bool(options.fails) == bool(options.artifact):
        analyseur.error("Choisissez exactement --fails ou --artifact.")

    racine = Path(options.root).resolve()
    verbose = not options.quiet
    candidats = collect_test_files(racine, options.pattern)

    if options.fails:
        cible = options.fails
        candidats = [c for c in candidats if c != cible]
        if not candidats:
            print("Aucun candidat.", file=sys.stderr)
            return 2

        if verbose:
            print(f"Vérification : « {cible} » passe-t-il seul ?", file=sys.stderr)
        if not target_passes_alone(cible, racine, options.timeout):
            print(f"« {cible} » échoue SEUL. Il n'y a pas de pollueur à "
                  "chercher : le défaut est dans ce test.", file=sys.stderr)
            return 2

        if verbose:
            print(f"{len(candidats)} candidats.", file=sys.stderr)

        if options.linear:
            coupables = linear(candidats, cible, racine, options.timeout, verbose)
            if not coupables:
                print("Aucun candidat seul ne reproduit l'échec.")
                return 0
            for coupable in coupables:
                print(f"POLLUEUR : {coupable}")
            return 1

        coupable = bisect(candidats, cible, racine, options.timeout, verbose)
        if coupable is None:
            print("L'échec ne se reproduit pas, ou aucun fichier seul ne "
                  "l'explique. Essayez --linear.")
            return 0
        print(f"POLLUEUR : {coupable}")
        print(f"Pour reproduire : python -m pytest {coupable} {cible}")
        return 1

    artefact = Path(options.artifact)
    if not artefact.is_absolute():
        artefact = racine / artefact
    coupable = find_artifact_creator(candidats, artefact, racine,
                                     options.timeout, verbose)
    if coupable is None:
        print(f"Aucun test ne crée « {options.artifact} ».")
        return 0
    print(f"POLLUEUR : {coupable}")
    print(f"Crée : {artefact}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
