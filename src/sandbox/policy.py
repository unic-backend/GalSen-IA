"""
Ce qu'un bac à sable borne, et ce qu'il ne borne pas (VOLET 34, ch. 08).

ADR-017 §5 : **aucune nouvelle capacité d'exécution ne livre sans son test
d'évasion.** La leçon vient d'OpenClaw — 280 000 étoiles, une base de confiance
minimale, des listes blanches, des conteneurs Docker durcis, et une littérature
publiée sur la façon d'en sortir. *Un bac à sable est une affirmation tant que
personne n'a essayé de s'en échapper.*

Ce fichier déclare donc, avant le code, ce qui est réellement garanti.

## Ce qui est borné, et vérifié par un test qui essaie de le franchir

| Limite | Ce qu'elle empêche |
|---|---|
| Temps processeur | Une boucle infinie qui occupe un cœur |
| Mémoire | Une allocation qui étouffe la machine |
| Nombre de processus | Une bombe de forks — **plafonnée, pas isolée** : voir ci-dessous |
| Taille des fichiers écrits | Un disque rempli |
| Durée totale | Un processus qui dort au lieu de calculer |
| Sortie capturée | Un flot qui remplit la mémoire du parent |
| **Environnement** | Le code exécuté ne voit **aucun secret** du processus parent |

## Ce qui n'est **pas** borné, et doit être dit

**Le système de fichiers.** Sans espaces de noms — donc sans privilèges que la
plateforme n'a pas — un processus fils lit et écrit là où l'utilisateur qui
l'exécute le peut. Le répertoire de travail est isolé et nettoyé ; ce n'est pas
une frontière, c'est un rangement.

**Le réseau.** Le couper demande la même chose.

Ces deux-là restent tenus par ce qui les tenait déjà : les racines déclarées
(ch. 07), le portillon d'approbation (ADR-006), et une liste blanche
d'exécutables. **Le bac à sable ne les remplace pas ; il les complète.** Le
présenter autrement serait exactement la promesse qu'OpenClaw n'a pas tenue.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

#: Variables d'environnement transmises au processus fils. Tout le reste est
#: retiré : le processus parent porte `GALSEN_API_KEYS`, `OPENAI_API_KEY`,
#: `GALSEN_SMTP_PASSWORD`… et un fils qui hérite de `os.environ` les lit tous.
ENVIRONNEMENT_TRANSMIS = ("PATH", "LANG", "LC_ALL", "TZ", "HOME", "TMPDIR")

#: Ce que le bac à sable **ne** garantit **pas**, énuméré pour être rapporté.
NON_GARANTI = (
    "filesystem: un fils lit et écrit là où l'utilisateur le peut ; le "
    "répertoire de travail est un rangement, pas une frontière",
    "network: aucune coupure réseau sans espaces de noms",
    "processes: RLIMIT_NPROC borne l'**utilisateur**, pas ce bac à sable. Une "
    "bombe de forks y est plafonnée, mais elle consomme le budget de processus "
    "de la plateforme elle-même. Le groupe est tué à la fin de chaque exécution "
    "pour que rien ne survive ; un vrai plafond par exécution demande des "
    "cgroups, donc des privilèges que la plateforme n'a pas.",
)


@dataclass(frozen=True)
class SandboxPolicy:
    """
    Les bornes d'une exécution.

    Attributes:
        cpu_seconds: Temps processeur maximal.
        memory_bytes: Mémoire adressable maximale.
        file_size_bytes: Taille maximale d'un fichier écrit.
        processes: Nombre maximal de processus de l'utilisateur — borne une
            bombe de forks.
        wall_seconds: Durée totale, horloge murale. Distincte du temps
            processeur : un programme qui dort n'en consomme pas.
        output_bytes: Sortie capturée au-delà de laquelle on tronque.
        environment: Variables transmises ; le reste est retiré.
    """

    cpu_seconds: int = 5
    memory_bytes: int = 256 * 1024 * 1024
    file_size_bytes: int = 10 * 1024 * 1024
    processes: int = 64
    wall_seconds: int = 15
    output_bytes: int = 64 * 1024
    environment: Tuple[str, ...] = ENVIRONNEMENT_TRANSMIS

    def env(self) -> Dict[str, str]:
        """
        Construit l'environnement du processus fils.

        Une liste blanche, jamais un retrait de ce qui semble sensible : la
        seconde approche oublie la variable ajoutée demain, et c'est celle-là
        qui fuit.
        """
        transmis = {
            nom: os.environ[nom] for nom in self.environment if nom in os.environ
        }
        # Sans `PATH`, un interpréteur lancé par son nom serait introuvable ;
        # le donner vide serait plus surprenant que de le donner minimal.
        transmis.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        return transmis

    def to_dict(self) -> Dict[str, object]:
        """Décrit la politique, limites et non-garanties comprises."""
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_bytes": self.memory_bytes,
            "file_size_bytes": self.file_size_bytes,
            "processes": self.processes,
            "wall_seconds": self.wall_seconds,
            "output_bytes": self.output_bytes,
            "environment_passed": list(self.environment),
            "not_guaranteed": list(NON_GARANTI),
        }


@dataclass
class SandboxResult:
    """Ce qu'une exécution a produit, et comment elle s'est terminée."""

    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    killed_by: Optional[str] = None
    truncated: bool = False
    duration_seconds: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Vraie seulement si le code s'est terminé de lui-même, sans erreur."""
        return self.exit_code == 0 and not self.timed_out and self.killed_by is None

    def to_dict(self) -> Dict[str, object]:
        """Sérialise le résultat."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "killed_by": self.killed_by,
            "truncated": self.truncated,
            "duration_seconds": round(self.duration_seconds, 3),
            "notes": self.notes,
        }
