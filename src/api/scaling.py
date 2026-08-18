"""
Inventaire de l'état local au processus (VOLET 02, ch. 10 — ADR-009).

Le chapitre 10 demande des services **sans état**, afin qu'une deuxième
instance puisse être démarrée derrière un répartiteur de charge sans rien
changer d'autre. La plateforme n'y est pas : plusieurs sous-systèmes gardent
leur état dans la mémoire du processus.

Ce module ne corrige pas cela — il le **mesure**. Une contrainte connue et
exposée se gère ; une contrainte implicite se découvre en production, le jour
où quelqu'un révoque une clé compromise et où celle-ci continue d'ouvrir les
autres instances.

`scaling_report()` répond à une seule question : « peut-on démarrer une
deuxième instance de cette plateforme aujourd'hui, et si non, qu'est-ce qui
casse en premier ? »
"""

import os
import socket
from dataclasses import dataclass
from typing import Any, Dict, List

INSTANCE_ID_VARIABLE = "GALSEN_INSTANCE_ID"
STORAGE_BACKEND_VARIABLE = "GALSEN_STORAGE_BACKEND"

# Portées possibles pour un élément d'état.
SCOPE_INSTANCE = "instance"
SCOPE_SHARED = "shared"

# Réserve commune à tout magasin SQLite partagé entre instances.
CAVEAT_SQLITE = (
    "SQLite suppose un disque local : le fichier partagé par un montage réseau "
    "ne garantit plus le verrouillage entre instances"
)


@dataclass(frozen=True)
class StateComponent:
    """
    Un sous-système et l'endroit où vit son état.

    Attributes:
        name: Identifiant stable du sous-système.
        scope: `instance` (état propre au processus) ou `shared` (magasin commun).
        detail: Où l'état réside concrètement.
        consequence: Ce qui se produit si une deuxième instance démarre.
        blocking: True quand la conséquence est une perte de correction ou de
            sécurité, et non une simple duplication sans effet.
        caveat: Réserve à connaître avant de considérer le point comme réglé.
    """

    name: str
    scope: str
    detail: str
    consequence: str
    blocking: bool
    caveat: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans champ vide inutile."""
        donnees: Dict[str, Any] = {
            "name": self.name,
            "scope": self.scope,
            "detail": self.detail,
            "consequence": self.consequence,
            "blocking": self.blocking,
        }
        if self.caveat:
            donnees["caveat"] = self.caveat
        return donnees


def instance_id() -> str:
    """
    Identifie l'instance qui répond.

    Sans cet identifiant, un rapport de santé collecté derrière un répartiteur
    de charge ne dit pas *quelle* instance il décrit — et deux rapports
    contradictoires deviennent indébrouillables.

    Returns:
        La valeur de `GALSEN_INSTANCE_ID` si elle est définie, sinon
        `<hôte>:<pid>`, qui suffit à distinguer deux processus.
    """
    declare = os.environ.get(INSTANCE_ID_VARIABLE, "").strip()
    if declare:
        return declare
    return f"{socket.gethostname()}:{os.getpid()}"


def _storage_backend() -> str:
    """
    Retourne le backend de stockage effectivement appliqué (ADR-005).

    Passe par `src/storage/paths.py`, qui est le point de décision unique : lire
    la variable ici ferait diverger l'inventaire de la réalité le jour où la
    règle de normalisation changerait.
    """
    from src.storage.paths import storage_backend

    return storage_backend()


def state_inventory() -> List[StateComponent]:
    """
    Inventorie où vit l'état de chaque sous-système.

    L'inventaire est recalculé à chaque appel : le backend de stockage se lit
    dans l'environnement, et une liste figée à l'import mentirait dès qu'un
    déploiement change ce réglage.

    Returns:
        Un composant par sous-système portant de l'état, dans l'ordre de
        gravité décroissante.
    """
    sqlite_actif = _storage_backend() == "sqlite"

    def magasin(nom: str, module: str, consequence: str) -> StateComponent:
        """Décrit un sous-système dont le magasin suit `GALSEN_STORAGE_BACKEND`.

        Ces services ont un magasin mémoire *et* un magasin SQLite (ADR-005) :
        leur portée dépend donc de la configuration, et un inventaire qui les
        annoncerait toujours locaux mentirait dès qu'on active la persistance.
        """
        if sqlite_actif:
            return StateComponent(
                name=nom,
                scope=SCOPE_SHARED,
                detail=f"{module} persisté en SQLite (ADR-005)",
                consequence="deux instances lisent le même état si elles voient le même fichier",
                blocking=False,
                caveat=CAVEAT_SQLITE,
            )
        return StateComponent(
            name=nom,
            scope=SCOPE_INSTANCE,
            detail=f"{module} en mémoire du processus",
            consequence=consequence,
            blocking=True,
            caveat=f"réglable : {STORAGE_BACKEND_VARIABLE}=sqlite (ADR-005)",
        )

    if sqlite_actif:
        moteurs = StateComponent(
            name="engine_state",
            scope=SCOPE_SHARED,
            detail="mémoire, modèles et connaissances persistés en SQLite (ADR-005)",
            consequence="deux instances lisent le même état si elles voient le même fichier",
            blocking=False,
            caveat=CAVEAT_SQLITE,
        )
    else:
        moteurs = StateComponent(
            name="engine_state",
            scope=SCOPE_INSTANCE,
            detail="mémoire, modèles et connaissances en mémoire du processus",
            consequence="ce qu'une instance mémorise est invisible pour les autres",
            blocking=True,
            caveat=f"réglable : {STORAGE_BACKEND_VARIABLE}=sqlite (ADR-005)",
        )

    return [
        StateComponent(
            name="api_key_revocations",
            scope=SCOPE_INSTANCE,
            detail="liste de révocation tenue en mémoire par RBACManager",
            consequence=(
                "une clé compromise révoquée sur une instance continue d'ouvrir "
                "les autres"
            ),
            blocking=True,
            caveat=(
                "un verrou d'instance interdit désormais une deuxième instance "
                "sur le même répertoire de données (ADR-013) ; la révocation ne "
                "survit toujours pas à un redémarrage, donc retirer la clé de "
                "GALSEN_API_KEYS reste le seul geste définitif"
            ),
        ),
        StateComponent(
            name="rate_limit_counters",
            scope=SCOPE_INSTANCE,
            detail="compteurs par client tenus par InMemoryRateLimiter",
            consequence=(
                "le quota réellement accordé est multiplié par le nombre "
                "d'instances"
            ),
            blocking=True,
        ),
        magasin(
            "uploaded_files",
            "magasin de fichiers (src/services/file/)",
            "un fichier téléversé n'existe que sur l'instance qui l'a reçu ; "
            "ailleurs il répond 404",
        ),
        magasin(
            "notifications",
            "magasin de notifications (src/services/notification/)",
            "un utilisateur ne voit que les notifications servies par "
            "l'instance qu'il a jointe",
        ),
        moteurs,
        StateComponent(
            name="connector_registry",
            scope=SCOPE_INSTANCE,
            detail="registre reconstruit au démarrage de chaque instance",
            consequence=(
                "aucune : la configuration des connecteurs vient de "
                "l'environnement, identique pour toutes les instances (ADR-007)"
            ),
            blocking=False,
        ),
        StateComponent(
            name="engine_registry",
            scope=SCOPE_INSTANCE,
            detail="EngineRegistry instancié une fois par processus",
            consequence="aucune : ce sont des objets de travail, pas de l'état métier",
            blocking=False,
        ),
    ]


def scaling_report() -> Dict[str, Any]:
    """
    Décrit la capacité de la plateforme à tourner en plusieurs instances.

    Returns:
        Un dictionnaire portant l'identifiant de l'instance, le verdict
        `multi_instance_ready`, la liste des sous-systèmes bloquants et
        l'inventaire complet.
    """
    # Import différé : `instance_lock` a besoin de `instance_id()`, défini ici.
    # L'importer en tête du module ferait un cycle.
    from src.api.instance_lock import status as etat_du_verrou

    composants = state_inventory()
    bloquants = [composant for composant in composants if composant.blocking]

    return {
        "instance": instance_id(),
        "multi_instance_ready": not bloquants,
        "deployment_model": "single-instance" if bloquants else "multi-instance",
        "blocking": [composant.name for composant in bloquants],
        "components": [composant.to_dict() for composant in composants],
        # Le verdict dit qu'une deuxième instance casserait quelque chose ; le
        # verrou dit si une deuxième instance peut seulement démarrer (ADR-013).
        # Vue réduite : `/health` n'est pas authentifiée, le chemin du verrou et
        # le PID de l'occupant n'y ont rien à faire.
        "instance_lock": {
            cle: valeur
            for cle, valeur in etat_du_verrou().items()
            if cle in ("held", "multi_instance_allowed", "enforced")
        },
        "reference": "ADR-009",
    }
