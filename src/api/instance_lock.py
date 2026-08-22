"""
Une seule instance à la fois sur un répertoire de données (ADR-009, ADR-013).

ADR-009 constate que plusieurs sous-systèmes gardent leur état dans la mémoire
du processus : les compteurs de débit et **la liste de révocation des clés**. La
conséquence est nommée depuis longtemps — « une clé compromise révoquée sur une
instance continue d'ouvrir les autres » — mais rien n'empêchait une deuxième
instance de démarrer. `docker compose up` en lançait même une sans le dire.

Ce module ferme cela par le seul moyen qui ne dépend pas de la vigilance de
l'opérateur : **au démarrage, l'application prend un verrou exclusif sur le
répertoire de données.** Une deuxième instance sur le même répertoire refuse de
démarrer et nomme celle qui tient la place.

Le verrou est posé par `flock` quand le système le fournit. C'est le bon
primitif : le noyau le relâche quand le processus meurt, quelle qu'en soit la
manière, donc il n'y a pas de verrou périmé à deviner. Deux conteneurs qui
montent le même volume verrouillent la même inode, ce qui est exactement le cas
que l'on veut interdire.

Deux limites, dites plutôt que tues :

- **Sur un montage réseau (NFS), `flock` n'est pas fiable.** C'est la même
  réserve que celle déjà portée par `scaling_report()` pour SQLite : ces deux
  garanties supposent un disque local.
- **Sous Windows, `msvcrt.locking` remplace `flock`** — même garantie : le noyau
  le relâche à la mort du processus. Ce n'était pas le cas avant le 2026-08-22 :
  le repli se contentait de tester l'existence du fichier, et fermer la fenêtre
  du serveur rendait tout redémarrage impossible sans suppression manuelle.
- **Sans `fcntl` ni `msvcrt`, la garantie est plus faible** : la présence du
  fichier suffit à refuser le démarrage, et un arrêt brutal laisse un fichier
  qu'un opérateur doit retirer. Le refus est explicite et dit quoi faire ;
  deviner qu'un PID est mort ferait courir un risque bien pire, celui de
  démarrer à côté d'une instance vivante.
"""

import json
import logging
import os
import socket
import time
from typing import Any, Dict, Optional

from src.api.scaling import instance_id

logger = logging.getLogger(__name__)

try:  # pragma: no cover - dépend du système, pas du code
    import msvcrt
except ImportError:
    msvcrt = None

try:  # pragma: no cover - dépend du système, pas du code
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

LOCK_FILENAME = "instance.lock"
DATA_DIR_VARIABLE = "GALSEN_DATA_DIR"
DEFAULT_DATA_DIR = "data"
ALLOW_MULTI_INSTANCE_VARIABLE = "GALSEN_ALLOW_MULTI_INSTANCE"

# Descripteur du verrou détenu par ce processus. Le verrou `flock` est attaché à
# la description de fichier ouverte : il faut donc garder ce descripteur ouvert
# aussi longtemps que l'instance vit.
_descripteur: Optional[int] = None
_chemin_detenu: Optional[str] = None


class InstanceAlreadyRunning(RuntimeError):
    """Une autre instance tient déjà le répertoire de données."""


def data_dir() -> str:
    """Retourne le répertoire de données de cette instance."""
    return os.getenv(DATA_DIR_VARIABLE, DEFAULT_DATA_DIR)


def lock_path() -> str:
    """Retourne le chemin du fichier verrou."""
    return os.path.join(data_dir(), LOCK_FILENAME)


def multi_instance_allowed() -> bool:
    """
    Indique si l'opérateur a levé le verrou sciemment.

    C'est le retour arrière de cette protection : `GALSEN_ALLOW_MULTI_INSTANCE=true`
    restaure le comportement d'avant, en connaissance de cause. Ce que cela
    coûte est écrit dans ADR-013 — au premier chef, une clé révoquée qui
    continue d'ouvrir les autres instances.
    """
    return os.getenv(ALLOW_MULTI_INSTANCE_VARIABLE, "").strip().lower() in (
        "true", "1", "yes",
    )


def read_holder(chemin: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Lit l'identité inscrite dans le fichier verrou.

    Le contenu est purement informatif : c'est le verrou du noyau qui décide,
    pas ce texte. Il sert à nommer l'instance en place dans le message de refus,
    car « impossible de démarrer » sans dire qui occupe la place n'est pas
    actionnable.

    Returns:
        Le contenu du verrou, ou None s'il est absent ou illisible.
    """
    cible = chemin or lock_path()
    try:
        with open(cible, "r", encoding="utf-8") as fichier:
            contenu = json.load(fichier)
    except (OSError, ValueError):
        return None
    return contenu if isinstance(contenu, dict) else None


def _identite() -> Dict[str, Any]:
    """Construit la fiche d'identité écrite dans le verrou."""
    return {
        "instance": instance_id(),
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _refus(chemin: str) -> InstanceAlreadyRunning:
    """Construit le refus de démarrage, en nommant l'occupant s'il est lisible."""
    occupant = read_holder(chemin)
    qui = occupant.get("instance", "inconnue") if occupant else "inconnue"
    depuis = f" depuis {occupant['started_at']}" if occupant and "started_at" in occupant else ""
    return InstanceAlreadyRunning(
        f"Une autre instance tient le répertoire de données : « {qui} »{depuis} "
        f"(verrou {chemin}). Deux instances sur le même répertoire, c'est deux "
        f"vérités : une clé révoquée sur l'une continue d'ouvrir l'autre, et le "
        f"quota réellement accordé est doublé. Arrêtez l'instance en place, ou "
        f"déclarez {ALLOW_MULTI_INSTANCE_VARIABLE}=true si c'est voulu (ADR-013)."
    )


def acquire() -> Dict[str, Any]:
    """
    Prend le verrou d'instance, ou refuse de démarrer.

    Réappeler la fonction dans le même processus ne repose pas le verrou : une
    instance ne peut pas être deux, et un second `flock` sur le même fichier
    depuis le même processus échouerait alors qu'il ne devrait pas.

    Returns:
        L'état du verrou, tel que `status()` le rapporte.

    Raises:
        InstanceAlreadyRunning: si une autre instance tient le répertoire.
    """
    global _descripteur, _chemin_detenu

    if _descripteur is not None:
        return status()

    if multi_instance_allowed():
        logger.warning(
            "%s=true : le verrou d'instance n'est pas pris. Les révocations de "
            "clés et les compteurs de quota ne valent plus que pour cette "
            "instance (ADR-013).",
            ALLOW_MULTI_INSTANCE_VARIABLE,
        )
        return status()

    chemin = lock_path()
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)

    if fcntl is None and msvcrt is not None:
        # Windows : `msvcrt.locking` est l'équivalent de `flock` — un verrou du
        # noyau, relâché à la mort du processus quelle qu'en soit la manière.
        #
        # La version précédente se contentait de « le fichier existe-t-il ? ».
        # Mesuré sur la machine du propriétaire le 2026-08-22 : fermer la
        # fenêtre du serveur tue le processus sans effacer le fichier, et
        # **GalSen IA ne redémarrait plus jamais** sans suppression manuelle.
        # Le commentaire d'origine acceptait « un faux positif coûte une
        # suppression manuelle » — mais sous Windows ce n'était pas un cas
        # limite : c'était le chemin normal, après chaque arrêt brutal.
        descripteur = os.open(chemin, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            msvcrt.locking(descripteur, msvcrt.LK_NBLCK, 1)
        except OSError:
            refus = _refus(chemin)
            os.close(descripteur)
            raise refus
        precedent = read_holder(chemin)
        if precedent and precedent.get("pid") != os.getpid():
            logger.warning(
                "Verrou repris à l'instance « %s » (pid %s), qui ne tourne plus.",
                precedent.get("instance", "inconnue"), precedent.get("pid", "?"),
            )
    elif fcntl is None:
        # Ni `fcntl` ni `msvcrt` : aucun verrou du noyau disponible. La présence
        # du fichier est le seul signal, et on refuse plutôt que de deviner.
        if os.path.exists(chemin):
            raise _refus(chemin)
        descripteur = os.open(chemin, os.O_RDWR | os.O_CREAT, 0o600)
    else:
        descripteur = os.open(chemin, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descripteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            refus = _refus(chemin)
            os.close(descripteur)
            raise refus

        # Le verrou est obtenu : ce que le fichier contenait décrivait une
        # instance qui n'est plus. Le dire, sinon un arrêt brutal reste invisible.
        precedent = read_holder(chemin)
        if precedent and precedent.get("pid") != os.getpid():
            logger.warning(
                "Verrou repris à l'instance « %s » (pid %s), qui ne tourne plus.",
                precedent.get("instance", "inconnue"), precedent.get("pid", "?"),
            )

    os.ftruncate(descripteur, 0)
    os.write(descripteur, json.dumps(_identite()).encode("utf-8"))
    os.fsync(descripteur)
    try:
        os.chmod(chemin, 0o600)
    except OSError:
        # Même tolérance que pour les bases : un système de fichiers sans
        # permissions POSIX ne doit pas empêcher le démarrage.
        pass

    _descripteur = descripteur
    _chemin_detenu = chemin
    logger.info("Verrou d'instance pris : %s (%s)", chemin, instance_id())
    return status()


def release() -> None:
    """
    Relâche le verrou et retire le fichier.

    Le noyau relâcherait `flock` de lui-même à la mort du processus ; ce qui
    compte ici est le **retrait du fichier**, car `scripts/backup.py` s'en sert
    pour refuser une restauration pendant qu'une instance tourne. Un fichier
    laissé derrière bloquerait la restauration sans raison.
    """
    global _descripteur, _chemin_detenu

    if _descripteur is None:
        return

    try:
        if fcntl is not None:
            fcntl.flock(_descripteur, fcntl.LOCK_UN)
        elif msvcrt is not None:
            os.lseek(_descripteur, 0, os.SEEK_SET)
            msvcrt.locking(_descripteur, msvcrt.LK_UNLCK, 1)
        os.close(_descripteur)
    except OSError as erreur:
        logger.warning("Verrou d'instance : libération incomplète (%s).", erreur)

    if _chemin_detenu:
        try:
            os.unlink(_chemin_detenu)
        except OSError:
            pass

    _descripteur = None
    _chemin_detenu = None


def held() -> bool:
    """Indique si ce processus tient le verrou."""
    return _descripteur is not None


def is_running(chemin: Optional[str] = None) -> bool:
    """
    Indique si une instance tient le verrou, vue depuis un autre processus.

    Utilisée par `scripts/backup.py`, qui refuse de restaurer par-dessus une
    base ouverte. La présence du fichier ne suffit pas à répondre : un arrêt
    brutal en laisse un derrière, et une restauration serait alors refusée pour
    toujours. On demande donc le verrou : l'obtenir prouve que personne ne le
    tient, et il est relâché aussitôt.

    Returns:
        True si une instance tient le verrou. En l'absence de `fcntl`, la
        présence du fichier est la seule réponse possible — plus prudente que
        juste.
    """
    cible = chemin or lock_path()
    if not os.path.exists(cible):
        return False
    if fcntl is None:  # pragma: no cover - dépend du système
        return True

    try:
        descripteur = os.open(cible, os.O_RDWR)
    except OSError:
        return True
    try:
        fcntl.flock(descripteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    else:
        fcntl.flock(descripteur, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descripteur)


def status() -> Dict[str, Any]:
    """
    Décrit l'état du verrou, pour `/health`.

    Returns:
        Le chemin du verrou, s'il est détenu par ce processus, l'identité
        inscrite, et si le mode multi-instance a été autorisé.
    """
    return {
        "path": lock_path(),
        "held": held(),
        "holder": read_holder(),
        "multi_instance_allowed": multi_instance_allowed(),
        "enforced": fcntl is not None,
    }
