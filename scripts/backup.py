#!/usr/bin/env python3
"""
Sauvegarde et restauration des bases SQLite de GalSen IA (ADR-005).

`docs/deployment/docker.md` proposait `cp -r` du volume de données. **Copier un
fichier SQLite ouvert peut produire une base corrompue** : l'écriture en cours
n'est pas atomique du point de vue du copieur, et depuis que les bases tournent
en mode WAL, les écritures récentes vivent dans un fichier `-wal` séparé qu'une
copie du seul `.sqlite` laisserait derrière.

`VACUUM INTO` règle les deux : SQLite écrit une copie **cohérente** de la base,
WAL compris, pendant que l'application continue d'écrire. C'est l'équivalent
transactionnel de la copie, et il ne demande aucune dépendance — la commande est
dans la bibliothèque standard depuis SQLite 3.27 (Python 3.11 embarque 3.34+).

Usage :

    python scripts/backup.py sauvegarder
    python scripts/backup.py sauvegarder --vers /chemin/sauvegardes
    python scripts/backup.py lister
    python scripts/backup.py restaurer 2026-08-11T18-30-00

La restauration **refuse de s'exécuter tant que l'application tourne** : écraser
une base ouverte est le meilleur moyen de perdre ce qu'on voulait sauver.
"""

import argparse
import datetime
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

# Exécuté en script, `sys.path[0]` est `scripts/` : la racine du dépôt doit être
# ajoutée pour que `src.api.instance_lock` soit importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Le répertoire de données et celui des sauvegardes suivent la configuration.
DATA_DIR_VARIABLE = "GALSEN_DATA_DIR"
BACKUP_DIR_VARIABLE = "GALSEN_BACKUP_DIR"
DEFAULT_DATA_DIR = "data"
DEFAULT_BACKUP_DIR = "data/backups"

# Nom du fichier verrou posé par une instance en cours d'exécution.
VERROU = "instance.lock"


def repertoire_donnees() -> Path:
    """Retourne le répertoire des bases."""
    return Path(os.getenv(DATA_DIR_VARIABLE, DEFAULT_DATA_DIR))


def repertoire_sauvegardes() -> Path:
    """Retourne le répertoire des sauvegardes."""
    return Path(os.getenv(BACKUP_DIR_VARIABLE, DEFAULT_BACKUP_DIR))


def bases(source: Path) -> List[Path]:
    """
    Retourne les bases à sauvegarder.

    Les fichiers `-wal` et `-shm` sont **exclus volontairement** : `VACUUM INTO`
    les intègre, et les copier séparément recréerait le problème qu'on évite.
    """
    return sorted(p for p in source.glob("*.sqlite") if p.is_file())


def horodatage() -> str:
    """Retourne un horodatage utilisable comme nom de répertoire."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def sauvegarder(destination: Path = None) -> Tuple[Path, List[str]]:
    """
    Copie chaque base dans un répertoire horodaté, à chaud.

    Args:
        destination: répertoire racine des sauvegardes.

    Returns:
        Le répertoire créé et la liste des bases sauvegardées.

    Raises:
        FileNotFoundError: si le répertoire de données n'existe pas.
    """
    source = repertoire_donnees()
    if not source.is_dir():
        raise FileNotFoundError(f"Répertoire de données introuvable : {source}")

    cible = (destination or repertoire_sauvegardes()) / horodatage()
    cible.mkdir(parents=True, exist_ok=True)
    # Une sauvegarde contient exactement ce que contient la base : elle mérite
    # les mêmes permissions.
    os.chmod(cible, 0o700)

    copiees = []
    for base in bases(source):
        arrivee = cible / base.name
        with sqlite3.connect(f"file:{base}?mode=ro", uri=True) as connexion:
            # `VACUUM INTO` échoue si le fichier existe déjà : c'est voulu, il
            # n'écrase jamais une sauvegarde.
            connexion.execute("VACUUM INTO ?", (str(arrivee),))
        os.chmod(arrivee, 0o600)
        copiees.append(base.name)

    return cible, copiees


def lister(racine: Path = None) -> List[Path]:
    """Retourne les sauvegardes existantes, de la plus récente à la plus ancienne."""
    base = racine or repertoire_sauvegardes()
    if not base.is_dir():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)


def instance_en_cours(source: Path) -> bool:
    """
    Indique si une instance tient le verrou du répertoire de données.

    La question est posée au verrou lui-même, pas à la présence du fichier : un
    arrêt brutal laisse un fichier derrière, et refuser la restauration pour un
    fichier orphelin bloquerait la seule manœuvre qui répare l'incident.
    """
    from src.api.instance_lock import is_running

    return is_running(str(source / VERROU))


def restaurer(nom: str, racine: Path = None) -> List[str]:
    """
    Remet en place les bases d'une sauvegarde.

    Args:
        nom: nom du répertoire de sauvegarde (voir `lister`).
        racine: répertoire racine des sauvegardes.

    Returns:
        Les noms des bases restaurées.

    Raises:
        FileNotFoundError: si la sauvegarde n'existe pas.
        RuntimeError: si une instance tourne encore.
    """
    sauvegarde = (racine or repertoire_sauvegardes()) / nom
    if not sauvegarde.is_dir():
        raise FileNotFoundError(f"Sauvegarde introuvable : {sauvegarde}")

    cible = repertoire_donnees()
    if instance_en_cours(cible):
        raise RuntimeError(
            "Une instance tourne encore (verrou présent dans le répertoire de "
            "données). Arrêtez-la avant de restaurer : écraser une base ouverte "
            "perd ce qu'on voulait sauver."
        )

    cible.mkdir(parents=True, exist_ok=True)
    restaurees = []
    for base in sorted(sauvegarde.glob("*.sqlite")):
        arrivee = cible / base.name
        # Les sidecars de l'ancienne base doivent partir : laissés en place, ils
        # décriraient des transactions qui n'existent plus dans le fichier
        # restauré.
        for suffixe in ("-wal", "-shm"):
            sidecar = Path(str(arrivee) + suffixe)
            if sidecar.exists():
                sidecar.unlink()
        shutil.copy2(base, arrivee)
        os.chmod(arrivee, 0o600)
        restaurees.append(base.name)

    return restaurees


def main() -> int:
    """Point d'entrée en ligne de commande."""
    analyseur = argparse.ArgumentParser(description=__doc__,
                                        formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = analyseur.add_subparsers(dest="commande", required=True)

    creer = sous.add_parser("sauvegarder", help="sauvegarde à chaud de toutes les bases")
    creer.add_argument("--vers", type=Path, default=None, help="répertoire racine des sauvegardes")

    sous.add_parser("lister", help="liste les sauvegardes existantes")

    remettre = sous.add_parser("restaurer", help="restaure une sauvegarde")
    remettre.add_argument("nom", help="nom du répertoire de sauvegarde")

    arguments = analyseur.parse_args()

    if arguments.commande == "sauvegarder":
        try:
            cible, copiees = sauvegarder(arguments.vers)
        except (FileNotFoundError, sqlite3.Error) as erreur:
            print(f"Échec de la sauvegarde : {erreur}", file=sys.stderr)
            return 1
        print(f"Sauvegarde dans {cible}")
        for nom in copiees:
            print(f"  {nom}")
        if not copiees:
            print("  aucune base trouvée — le stockage est-il en mémoire ?")
        return 0

    if arguments.commande == "lister":
        sauvegardes = lister()
        if not sauvegardes:
            print("Aucune sauvegarde.")
            return 0
        for chemin in sauvegardes:
            nombre = len(list(chemin.glob("*.sqlite")))
            print(f"{chemin.name}  ({nombre} base(s))")
        return 0

    try:
        restaurees = restaurer(arguments.nom)
    except (FileNotFoundError, RuntimeError) as erreur:
        print(f"Échec de la restauration : {erreur}", file=sys.stderr)
        return 1
    print(f"{len(restaurees)} base(s) restaurée(s) : {', '.join(restaurees)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
