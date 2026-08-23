"""
Exécuter du code écrit par un agent, sous contrainte (VOLET 34, ch. 08).

L'outil Docker de la plateforme est désactivé pour une raison écrite : depuis le
conteneur de production, il exigerait le socket Docker de l'hôte, c'est-à-dire
root sur l'hôte. Le remplacer par « on le réactive » n'était donc pas une option,
et ce module prend l'autre chemin : **borner ce que le code peut consommer et
voir**, avec des limites que le noyau applique et qu'un test essaie de franchir.

## Pourquoi les limites du noyau plutôt qu'un conteneur

`setrlimit` est appliqué par le noyau au processus fils, avant l'exécution du
code. Rien de ce que le code fait ensuite ne les lève : ce sont des bornes dures,
pas des vérifications qu'un appelant pourrait contourner.

Ce que cela ne donne pas — isolation du système de fichiers et du réseau — est
énuméré dans `policy.NON_GARANTI` et rapporté par `describe()`. Un bac à sable
qui laisse croire à une frontière qu'il n'a pas est plus dangereux que pas de bac
à sable du tout : on lui confie ce qu'on n'aurait pas confié.
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional

from .policy import NON_GARANTI, SandboxPolicy, SandboxResult

# `resource` n'existe que sur les systèmes POSIX. L'importer en haut de fichier
# faisait échouer **tout** `import src.api.server` sous Windows — mesuré sur la
# machine du propriétaire le 2026-08-22 : `ModuleNotFoundError: No module named
# 'resource'`, et la plateforme entière refusait de démarrer.
#
# Le module prévoyait déjà ce cas (`unavailable_reason()` refuse sur Windows) ;
# c'est l'import qui échouait **avant** que cette garde puisse servir. Un
# `try/except` ici la laisse faire son travail, et `run()` refuse toujours.
try:
    import resource
except ImportError:  # pragma: no cover — dépend du système, pas du code
    resource = None

logger = logging.getLogger(__name__)

#: Signaux dont le nom est rendu tel quel quand le noyau tue le processus.
SIGNAUX = {
    9: "SIGKILL",
    11: "SIGSEGV",
    24: "SIGXCPU (temps processeur dépassé)",
    25: "SIGXFSZ (fichier trop grand)",
}


class SandboxUnavailable(RuntimeError):
    """Le bac à sable ne peut pas s'appliquer ici, et la raison l'accompagne."""


def unavailable_reason() -> Optional[str]:
    """
    Retourne pourquoi le bac à sable ne peut pas servir, ou None s'il le peut.

    Sur Windows, `resource` n'existe pas : exécuter quand même reviendrait à
    lancer du code d'agent **sans aucune borne** en croyant en avoir. Refuser est
    le seul comportement honnête tant qu'un équivalent n'est pas écrit.

    **Deux conditions, et l'ordre n'est pas indifférent.** Windows d'abord, parce
    qu'un test existant simule Windows en remplaçant `platform.system()` et que
    remplacer ce contrôle par le seul « `resource` est-il là ? » l'aurait rendu
    silencieusement inopérant — une garde de sécurité rétrécie sans que personne
    le voie. C'est arrivé le 2026-08-22 et le test l'a attrapé.

    L'absence du module ensuite, parce qu'un système POSIX exotique sans
    `resource` mérite la même réponse : ce qui compte est l'absence des bornes,
    pas seulement le nom de la plateforme.
    """
    if platform.system() == "Windows":
        return (
            "Les limites du noyau (`setrlimit`) n'existent pas sur Windows. "
            "Exécuter sans elles reviendrait à croire à des bornes absentes ; "
            "un équivalent (Job Objects) reste à écrire."
        )
    if resource is None:
        return (
            "Le module `resource` est absent de cet interpréteur, donc "
            "`setrlimit` est inapplicable. Exécuter sans bornes en croyant en "
            "avoir est précisément ce que ce refus empêche."
        )
    return None


def describe(policy: Optional[SandboxPolicy] = None) -> Dict[str, object]:
    """
    Décrit ce que le bac à sable garantit, et ce qu'il ne garantit pas.

    C'est ce qu'un opérateur — ou un agent — doit pouvoir lire avant de confier
    du code, plutôt que de le déduire d'un échec.
    """
    politique = policy or SandboxPolicy()
    raison = unavailable_reason()
    return {
        "available": raison is None,
        "reason": raison,
        "policy": politique.to_dict(),
        "not_guaranteed": list(NON_GARANTI),
    }


def _appliquer_limites(policy: SandboxPolicy):
    """
    Retourne la fonction appliquée dans le fils, avant l'exécution du code.

    Elle tourne entre `fork` et `exec` : les limites sont donc en place avant que
    la première instruction du code de l'agent ne s'exécute.
    """

    def preparer() -> None:
        # Limite souple **inférieure** à la limite dure : le noyau envoie
        # d'abord SIGXCPU, dont le nom dit la cause, au lieu du SIGKILL muet
        # qu'une limite unique produit. Rapporter « SIGKILL » pour un
        # dépassement de temps processeur enverrait chercher une fuite mémoire.
        resource.setrlimit(
            resource.RLIMIT_CPU, (policy.cpu_seconds, policy.cpu_seconds + 1)
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (policy.file_size_bytes, policy.file_size_bytes)
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (policy.processes, policy.processes))
        # Pas de fichier de vidage mémoire : il porterait le contenu de la
        # mémoire du processus sur le disque.
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if policy.memory_bytes:
            resource.setrlimit(
                resource.RLIMIT_AS, (policy.memory_bytes, policy.memory_bytes)
            )
        # Nouveau groupe de processus : le délai d'attente tue le groupe entier,
        # donc aussi ce que le code aurait lancé.
        os.setsid()

    return preparer


def run(
    argv: List[str],
    policy: Optional[SandboxPolicy] = None,
    workdir: Optional[str] = None,
    stdin_text: str = "",
) -> SandboxResult:
    """
    Exécute une commande sous les bornes de la politique.

    Args:
        argv: Commande sous forme de liste — jamais une chaîne, jamais un shell.
        policy: Bornes appliquées ; les valeurs par défaut sinon.
        workdir: Répertoire de travail ; un répertoire temporaire, créé et
            nettoyé, sinon.
        stdin_text: Entrée standard fournie au processus.

    Returns:
        Le résultat, avec la cause de fin quand le noyau a interrompu.

    Raises:
        SandboxUnavailable: Les bornes ne peuvent pas s'appliquer sur ce système.
        ValueError: Commande absente ou mal formée.
    """
    raison = unavailable_reason()
    if raison is not None:
        raise SandboxUnavailable(raison)
    if not argv or not isinstance(argv, (list, tuple)):
        raise ValueError("Une commande est requise, sous forme de liste d'arguments.")

    politique = policy or SandboxPolicy()
    temporaire = workdir is None
    repertoire = workdir or tempfile.mkdtemp(prefix="galsen-sandbox-")
    debut = time.perf_counter()

    try:
        processus = subprocess.Popen(  # noqa: S603 - argv, jamais de shell
            list(argv),
            cwd=repertoire,
            env=politique.env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=_appliquer_limites(politique),
            text=True,
        )
    except OSError as erreur:
        raise SandboxUnavailable(f"Impossible de démarrer le processus : {erreur}")

    resultat = SandboxResult()
    try:
        sortie, erreur_standard = processus.communicate(
            input=stdin_text, timeout=politique.wall_seconds
        )
    except subprocess.TimeoutExpired:
        _tuer_le_groupe(processus)
        sortie, erreur_standard = processus.communicate()
        resultat.timed_out = True
        resultat.notes.append(
            f"Interrompu après {politique.wall_seconds} s d'horloge murale."
        )
    finally:
        # Le groupe est tué **quelle que soit** la façon dont l'exécution s'est
        # terminée, pas seulement sur délai dépassé.
        #
        # Trouvé par le test d'évasion, et c'était un vrai défaut : quand le
        # noyau tue le processus par une limite — temps processeur, mémoire —
        # ses descendants lui survivent. Une bombe de forks laissait donc des
        # processus vivants après la fin de l'exécution, et comme `RLIMIT_NPROC`
        # borne l'**utilisateur** et non le bac à sable, la plateforme elle-même
        # ne pouvait plus lancer de processus. Ce n'était pas une élévation de
        # privilège : c'était un déni de service contre le parent, ce qui suffit.
        _tuer_le_groupe(processus)
        if temporaire:
            shutil.rmtree(repertoire, ignore_errors=True)

    resultat.duration_seconds = time.perf_counter() - debut
    resultat.exit_code = processus.returncode
    resultat.stdout, tronque_sortie = _tronquer(sortie, politique.output_bytes)
    resultat.stderr, tronque_erreur = _tronquer(erreur_standard, politique.output_bytes)
    resultat.truncated = tronque_sortie or tronque_erreur

    if processus.returncode is not None and processus.returncode < 0:
        signal_recu = -processus.returncode
        resultat.killed_by = SIGNAUX.get(signal_recu, f"signal {signal_recu}")
        resultat.notes.append(f"Terminé par le noyau : {resultat.killed_by}.")

    return resultat


def run_python(
    code: str,
    policy: Optional[SandboxPolicy] = None,
    workdir: Optional[str] = None,
) -> SandboxResult:
    """
    Exécute du code Python écrit par un agent.

    Le code passe par l'**entrée standard** de l'interpréteur, pas par un fichier
    ni par `-c` : il ne traverse donc jamais une ligne de commande, où un
    caractère mal placé pourrait devenir un argument.

    Args:
        code: Source Python.
        policy: Bornes appliquées.
        workdir: Répertoire de travail.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Un code non vide est requis.")
    return run([sys.executable, "-I", "-"], policy=policy, workdir=workdir, stdin_text=code)


def _tuer_le_groupe(processus: subprocess.Popen) -> None:
    """
    Tue le groupe de processus lancé par cette exécution.

    L'identifiant du groupe **est** le pid du fils : `preparer()` appelle
    `os.setsid()`, ce qui en fait le chef de sa propre session. C'est ce qui
    permet de tuer le groupe *après* la mort du père.

    La première version demandait `os.getpgid(pid)`, qui lève une fois le père
    disparu — donc précisément dans le cas qui compte, quand le noyau vient de le
    tuer. Mesuré : cinq enfants survivaient à un père terminé par SIGXCPU. Le
    repli sur `processus.kill()` ne rattrapait rien, puisque le père était déjà
    mort.
    """
    import signal

    try:
        os.killpg(processus.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        # Le groupe est déjà vide : il n'y a rien à tuer, et c'est le cas normal
        # d'un code qui s'est terminé de lui-même.
        pass


def _tronquer(texte: Optional[str], limite: int) -> tuple:
    """Tronque une sortie trop longue, en le disant."""
    if not texte:
        return "", False
    if len(texte) <= limite:
        return texte, False
    return texte[:limite] + f"\n… tronqué à {limite} caractères.", True
