"""
Résolution du magasin et des chemins SQLite (ADR-005).

Le répertoire de données est configurable via `GALSEN_DATA_DIR` (défaut :
`data`), et le magasin par `GALSEN_STORAGE_BACKEND` (`in-memory` par défaut,
`sqlite` pour persister).

Ce module porte **le seul point de décision** du magasin. Le test
`os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").lower() == "sqlite"` était
réécrit dans huit gestionnaires — mémoire, modèle, connaissance, notification,
e-mail, calendrier, fichier, cloud. Huit copies d'une même règle finissent par
diverger, et ce dépôt a déjà payé quatre fois ce mode de défaillance : une seule
d'entre elles corrigée laisse les sept autres se tromper en silence.
"""

import os
import sqlite3

# Valeurs acceptées, dans l'ordre où elles sont documentées.
BACKENDS = ("in-memory", "sqlite")
BACKEND_VARIABLE = "GALSEN_STORAGE_BACKEND"
DEFAULT_BACKEND = "in-memory"


def storage_backend() -> str:
    """
    Retourne le magasin demandé par la configuration.

    Returns:
        `"sqlite"` ou `"in-memory"`. Une valeur inconnue retombe sur le défaut —
        `src/config/environment.py` la signale déjà au démarrage, et deviner
        « sqllite » ferait persister des données là où l'opérateur croit avoir
        un magasin volatile, ou l'inverse.
    """
    valeur = os.getenv(BACKEND_VARIABLE, DEFAULT_BACKEND).strip().lower()
    return valeur if valeur in BACKENDS else DEFAULT_BACKEND


def declared_backend() -> str:
    """
    Retourne la valeur **déclarée**, sans normalisation.

    `storage_backend()` retombe sur le défaut quand la valeur est inconnue, ce
    qui est le bon comportement à l'exécution. Mais un rapport de santé qui ne
    verrait que la valeur normalisée dirait « stockage : in-memory, tout va
    bien » à un opérateur ayant écrit `postgresql` — la configuration ignorée
    deviendrait invisible au moment précis où elle doit se voir.
    """
    return os.getenv(BACKEND_VARIABLE, DEFAULT_BACKEND).strip().lower()


def sqlite_enabled() -> bool:
    """Indique si les magasins doivent persister sur disque."""
    return storage_backend() == "sqlite"


def prepare_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """
    Applique les PRAGMA communs à toute connexion SQLite de la plateforme.

    `journal_mode=WAL` n'était posé nulle part : le mode par défaut (`DELETE`)
    fait que lecteurs et écrivain se bloquent mutuellement, et qu'un arrêt
    brutal en cours d'écriture laisse un journal à rejouer. WAL supprime les
    deux, et c'est la condition d'une sauvegarde à chaud.

    `synchronous=NORMAL` est le compagnon habituel de WAL : avec WAL, un arrêt
    du système ne peut pas corrompre la base à ce niveau, seule la dernière
    transaction peut être perdue — un compromis que `FULL` paie à chaque
    écriture.

    Args:
        conn: la connexion à préparer.

    Returns:
        La même connexion, PRAGMA appliqués.
    """
    # L'attente d'abord : les PRAGMA qui suivent peuvent avoir à patienter, et
    # sans ce réglage ils échoueraient immédiatement sur « database is locked ».
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")

    # `journal_mode` est une propriété **de la base**, inscrite dans son en-tête,
    # pas de la connexion : une fois posé il vaut pour toutes les connexions
    # suivantes. Le poser à chaque ouverture demandait un verrou exclusif que
    # les autres connexions ouvertes refusaient — mesuré, une restauration
    # pendant qu'un gestionnaire tenait la base échouait sur
    # « database is locked ».
    #
    # On ne le pose donc que s'il n'est pas déjà WAL, et un échec n'est pas
    # fatal : soit une autre connexion l'a déjà fait, soit la base est sur un
    # système de fichiers qui ne supporte pas WAL (certains montages réseau),
    # auquel cas le mode par défaut reste correct — seulement moins concurrent.
    try:
        if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass
    return conn


def secure_database_file(chemin: str) -> None:
    """
    Restreint un fichier de base à son propriétaire.

    Une base contient des mémoires, des connaissances et des e-mails ; elle était
    créée en 0644, donc lisible par tout compte de la machine. Le fichier est
    ramené à 0600. L'échec n'est pas fatal — un système de fichiers sans
    permissions POSIX (montage Windows, certains volumes) ne doit pas empêcher
    la plateforme de démarrer.
    """
    if chemin == ":memory:":
        return
    try:
        os.chmod(chemin, 0o600)
    except OSError:
        pass


def data_dir() -> str:
    """
    Retourne le répertoire de données de la plateforme.

    Tous les magasins écrivent là — bases SQLite, verrou d'instance, fichiers
    déposés (ADR-016). La variable était lue directement à plusieurs endroits,
    et ce module existe pour que ce genre de règle n'ait qu'un seul endroit.

    Returns:
        `GALSEN_DATA_DIR`, ou `data` par défaut.
    """
    return os.getenv("GALSEN_DATA_DIR", "data")


def default_sqlite_path(filename: str) -> str:
    """
    Résout le chemin par défaut d'un fichier SQLite.

    Args:
        filename: Nom du fichier SQLite (exemple : "models.sqlite").

    Returns:
        Chemin complet dans le répertoire de données configuré.
    """
    return os.path.join(data_dir(), filename)
