"""
Lancement des moteurs de codage, sous le bac à sable de la plateforme (ADR-028).

Ce module ne lance rien lui-même. Il **traduit** : d'un côté le besoin d'un
adaptateur — une commande, un dossier, des variables, une borne de temps — de
l'autre `src/sandbox.run()`, qui applique les limites du noyau et tue le groupe
de processus quoi qu'il arrive.

C'est une réécriture volontaire. La première version portait sa propre boucle
`subprocess` avec `start_new_session`, un délai et un `SIGTERM`/`SIGKILL`. Elle
marchait, et elle était **moins bonne** que le bac à sable déjà présent :
celui-ci ajoute `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE` et `RLIMIT_NPROC`, il
nettoie le groupe même quand le noyau a tué le processus par une limite — un
défaut trouvé là-bas par un test d'évasion — et il refuse de s'exécuter sur
Windows plutôt que de croire à des bornes absentes.

Deux vocabulaires pour un geste dérivent, et ce dépôt l'a déjà payé quatre fois.
Il n'en reste qu'un.

## Les bornes propres au codage

Les bornes par défaut du bac à sable visent un fragment de code d'agent :
5 s de processeur, 256 Mio, 15 s d'horloge. Un moteur de codage charge litellm,
lit un dépôt et attend un modèle : il les franchirait toutes en démarrant.
`politique_de_codage()` les élargit, et **c'est le seul endroit** où ces
chiffres existent — un adaptateur ne choisit pas ses propres limites.

Ce qui n'est pas élargi : la borne d'horloge reste celle de la tâche, donc
finie ; et l'environnement reste une liste blanche.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from src.sandbox.policy import SandboxPolicy
from src.sandbox.runner import SandboxUnavailable, run as run_sandbox

# Un extrait de sortie sert au diagnostic, pas à l'archivage. Plus large que le
# défaut du bac à sable (64 Kio) : la sortie d'aider porte la configuration
# effective du modèle, et c'est en la lisant qu'on voit pourquoi il n'a rien fait.
TAILLE_SORTIE = 256 * 1024

# Ce qu'un moteur de codage consomme réellement, et qui dépasse de loin les
# bornes d'un fragment de code d'agent :
#
# - processeur : lire un dépôt et construire une carte de contexte prend des
#   secondes de calcul, pas des millisecondes ;
# - mémoire : litellm, tree-sitter et les dépendances d'aider dépassent 1 Gio ;
# - fichiers : un moteur peut écrire un journal ou un correctif volumineux.
#
# Ces valeurs restent des **bornes** : elles arrêtent une fuite, elles ne
# prétendent pas isoler. Ce que le bac à sable ne garantit pas est énuméré dans
# `src/sandbox/policy.py`, et n'est pas moins vrai ici.
PROCESSEUR_SECONDES = 3600
MEMOIRE_OCTETS = 4 * 1024 * 1024 * 1024
TAILLE_FICHIER_OCTETS = 512 * 1024 * 1024
PROCESSUS = 512


@dataclass(frozen=True)
class ProcessResult:
    """
    Ce qu'une exécution de moteur a donné.

    Attributes:
        argv: La commande lancée.
        exit_code: Code de sortie ; `None` si le processus n'a jamais démarré.
        stdout: Sortie standard, bornée.
        stderr: Sortie d'erreur, bornée.
        timed_out: Vrai si la borne d'horloge a été atteinte.
        duration_seconds: Durée réelle.
        started: Faux si l'exécutable est introuvable, ou si le bac à sable ne
            peut pas s'appliquer sur ce système.
        error: Le motif quand le processus n'a pas démarré.
        killed_by: Le signal, quand le noyau a interrompu — une limite franchie
            se lit ici et nulle part ailleurs.
    """

    argv: List[str]
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    started: bool = True
    error: str = ""
    killed_by: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Vrai si le processus a démarré, fini dans les temps, et réussi."""
        return (
            self.started
            and not self.timed_out
            and self.killed_by is None
            and self.exit_code == 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Sérialise le résultat, sans jamais rendre la commande complète.

        Les arguments peuvent porter une clé d'API — SWE-agent en accepte une en
        ligne de commande. Seul le nom de l'exécutable est conservé.
        """
        return {
            "command": self.argv[0] if self.argv else "",
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "killed_by": self.killed_by,
            "started": self.started,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_excerpt": self.stdout,
            "stderr_excerpt": self.stderr,
            "error": self.error,
        }


def politique_de_codage(
    timeout_seconds: int,
    extra_environment: Optional[Mapping[str, str]] = None,
) -> SandboxPolicy:
    """
    Construit les bornes d'une exécution de moteur de codage.

    Args:
        timeout_seconds: Borne d'horloge, strictement positive.
        extra_environment: Variables fournies explicitement au moteur —
            typiquement l'adresse et la clé du service de modèles. Elles ne
            passent ni par `os.environ` ni par la ligne de commande.

    Returns:
        La politique à passer au bac à sable.

    Raises:
        ValueError: Délai nul ou négatif. Ce serait une attente sans fin
            déguisée, et la consigne de test l'interdit nommément.
    """
    if timeout_seconds <= 0:
        raise ValueError("Le délai d'exécution doit être strictement positif.")
    return SandboxPolicy(
        cpu_seconds=PROCESSEUR_SECONDES,
        memory_bytes=MEMOIRE_OCTETS,
        file_size_bytes=TAILLE_FICHIER_OCTETS,
        processes=PROCESSUS,
        wall_seconds=timeout_seconds,
        output_bytes=TAILLE_SORTIE,
        extra_environment=tuple(
            (nom, valeur)
            for nom, valeur in (extra_environment or {}).items()
            if valeur is not None
        ),
    )


def run_process(
    argv: List[str],
    cwd: Any,
    timeout_seconds: int,
    extra_environment: Optional[Mapping[str, str]] = None,
    stdin_text: str = "",
) -> ProcessResult:
    """
    Lance un moteur de codage sous les bornes du bac à sable.

    Args:
        argv: La commande et ses arguments. Jamais une chaîne, jamais un shell.
        cwd: Dossier de travail — l'espace de travail confié à la tâche.
        timeout_seconds: Borne d'horloge, strictement positive.
        extra_environment: Variables fournies au moteur.
        stdin_text: Entrée standard éventuelle.

    Returns:
        Le résultat. La fonction ne lève pas pour une commande introuvable ni
        pour un bac à sable inapplicable : les deux deviennent `started=False`
        avec leur motif, parce qu'un adaptateur doit pouvoir les rapporter à
        l'appelant au lieu de les laisser remonter.

    Raises:
        ValueError: Commande vide, ou délai non positif.
    """
    if not argv:
        raise ValueError("Aucune commande à exécuter.")

    politique = politique_de_codage(timeout_seconds, extra_environment)
    debut = time.time()
    try:
        resultat = run_sandbox(
            list(argv), policy=politique, workdir=str(cwd), stdin_text=stdin_text
        )
    except SandboxUnavailable as erreur:
        return ProcessResult(
            argv=list(argv), started=False, duration_seconds=time.time() - debut,
            error=str(erreur),
        )

    return ProcessResult(
        argv=list(argv),
        exit_code=resultat.exit_code,
        stdout=resultat.stdout,
        stderr=resultat.stderr,
        timed_out=resultat.timed_out,
        duration_seconds=resultat.duration_seconds,
        killed_by=resultat.killed_by,
    )
