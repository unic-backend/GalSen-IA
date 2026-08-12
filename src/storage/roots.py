"""
Les racines que la plateforme a le droit de toucher (VOLET 34, ch. 07).

Le brief demande de naviguer sur `C:\\`, sur des disques externes et dans des
dossiers de projets. L'outil de fichiers sait déjà se confiner à **une** racine,
et le fait bien : chemins absolus, `..` et liens symboliques sont tous résolus
avant la moindre opération.

Ce qui manquait n'est donc pas la sécurité — c'est de pouvoir en **déclarer
plusieurs**, et ce module ne fait que cela.

## Ce qu'il refuse de faire

**Élargir la racine à la machine entière.** « Donner accès au disque » et
« déclarer trois répertoires » se ressemblent une minute et divergent le jour où
un agent se trompe. Une racine est nommée, déclarée par l'opérateur, et rien
n'est joignable en dehors.

**Laisser l'appelant désigner sa racine.** Les racines viennent de la
configuration, jamais d'une requête. ADR-016 a mesuré le prix de l'inverse la
semaine dernière : `CloudFileItem.provider` enregistrait ce que l'appelant
croyait, et la plateforme le rapportait comme un fait.

## La déclaration

    GALSEN_STORAGE_ROOTS=projets:/home/awa/projets:rw,archives:/mnt/disque:ro

Trois champs par racine — nom, chemin, mode — séparés par des deux-points. Le
mode vaut `ro` par défaut : une racine déclarée sans intention explicite d'y
écrire est une racine en lecture seule.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VARIABLE = "GALSEN_STORAGE_ROOTS"

#: Modes acceptés dans la déclaration.
MODES = ("ro", "rw")


class RootRefused(PermissionError):
    """Un chemin ne tombe dans aucune racine déclarée, ou la racine est en lecture seule."""


@dataclass(frozen=True)
class Root:
    """
    Une racine déclarée.

    Attributes:
        name: Nom court, celui que l'humain lira dans une demande d'approbation.
        path: Chemin réel, résolu, sans lien symbolique.
        writable: L'écriture y est-elle autorisée.
    """

    name: str
    path: str
    writable: bool = False

    def to_dict(self) -> Dict[str, object]:
        """Sérialise la racine."""
        return {"name": self.name, "path": self.path, "writable": self.writable}


def declared_roots(declaration: Optional[str] = None) -> List[Root]:
    """
    Lit les racines déclarées.

    Args:
        declaration: Déclaration à lire ; `GALSEN_STORAGE_ROOTS` sinon.

    Returns:
        Les racines valides. Une entrée malformée ou pointant vers un répertoire
        inexistant est **signalée et écartée**, jamais devinée : deviner une
        racine reviendrait à donner accès à un répertoire que personne n'a
        déclaré.
    """
    brut = declaration if declaration is not None else os.getenv(VARIABLE, "")
    racines: List[Root] = []
    vus = set()

    for entree in brut.split(","):
        entree = entree.strip()
        if not entree:
            continue

        morceaux = entree.split(":")
        # Sur Windows, « C: » est un préfixe de lecteur : le chemin peut donc
        # contenir un deux-points. Le nom est le premier champ, le mode le
        # dernier quand il en est un, et le reste est le chemin.
        if len(morceaux) < 2:
            logger.error("Racine « %s » ignorée : forme attendue nom:chemin[:ro|rw].", entree)
            continue

        nom = morceaux[0].strip()
        mode = "ro"
        reste = morceaux[1:]
        if len(reste) > 1 and reste[-1].strip().lower() in MODES:
            mode = reste[-1].strip().lower()
            reste = reste[:-1]
        chemin = ":".join(reste).strip()

        if not nom or not chemin:
            logger.error("Racine « %s » ignorée : nom ou chemin vide.", entree)
            continue
        if nom in vus:
            logger.error("Racine « %s » ignorée : ce nom est déjà déclaré.", nom)
            continue
        if not os.path.isdir(chemin):
            logger.error(
                "Racine « %s » ignorée : « %s » n'est pas un répertoire existant.",
                nom, chemin,
            )
            continue

        vus.add(nom)
        racines.append(Root(name=nom, path=os.path.realpath(chemin), writable=mode == "rw"))

    return racines


def resolve(chemin: str, racines: List[Root], pour_ecriture: bool = False) -> Tuple[Root, str]:
    """
    Résout un chemin dans les racines déclarées.

    La résolution passe par `realpath` **avant** la comparaison : un lien
    symbolique qui sort d'une racine est donc refusé comme un `..` le serait.

    Args:
        chemin: Chemin demandé, absolu ou relatif à une racine (`projets/x.txt`).
        racines: Racines déclarées.
        pour_ecriture: Exiger que la racine autorise l'écriture.

    Returns:
        La racine qui contient le chemin, et le chemin absolu résolu.

    Raises:
        RootRefused: Aucun racine ne contient ce chemin, ou elle est en lecture
            seule alors qu'une écriture est demandée.
    """
    if not chemin or not str(chemin).strip():
        raise RootRefused("Un chemin est requis.")
    if not racines:
        raise RootRefused(
            f"Aucune racine déclarée. Renseigner {VARIABLE}, "
            "par exemple « projets:/home/awa/projets:rw »."
        )

    demande = str(chemin).strip()

    # Un chemin préfixé du nom d'une racine — « projets/rapport.txt » — est
    # résolu dans celle-ci. C'est la forme qu'un agent lit et écrit le plus
    # naturellement quand plusieurs racines existent.
    for racine in racines:
        prefixe = racine.name + os.sep
        alternatif = racine.name + "/"
        if demande.startswith(prefixe) or demande.startswith(alternatif):
            relatif = demande[len(racine.name) + 1:]
            return _verifier(racine, os.path.join(racine.path, relatif), pour_ecriture)

    candidat = demande if os.path.isabs(demande) else None
    if candidat is None:
        # Chemin relatif sans nom de racine : il n'est accepté que s'il n'y a
        # qu'une racine. Deviner laquelle parmi plusieurs écrirait au hasard.
        if len(racines) != 1:
            raise RootRefused(
                f"Chemin « {demande} » ambigu : {len(racines)} racines sont "
                "déclarées. Le préfixer du nom de la racine, par exemple "
                f"« {racines[0].name}/{demande} »."
            )
        candidat = os.path.join(racines[0].path, demande)

    resolu = os.path.realpath(candidat)
    for racine in racines:
        if resolu == racine.path or resolu.startswith(racine.path + os.sep):
            return _verifier(racine, resolu, pour_ecriture)

    raise RootRefused(
        f"Accès refusé : « {demande} » est hors des racines déclarées "
        f"({', '.join(racine.name for racine in racines)})."
    )


def _verifier(racine: Root, candidat: str, pour_ecriture: bool) -> Tuple[Root, str]:
    """Résout un candidat et vérifie qu'il reste dans sa racine."""
    resolu = os.path.realpath(candidat)
    if resolu != racine.path and not resolu.startswith(racine.path + os.sep):
        # Le cas du lien symbolique qui sort : le nom de la racine était bon,
        # la destination ne l'est pas.
        raise RootRefused(
            f"Accès refusé : « {candidat} » sort de la racine « {racine.name} »."
        )
    if pour_ecriture and not racine.writable:
        raise RootRefused(
            f"Racine « {racine.name} » déclarée en lecture seule : aucune "
            "écriture n'y est possible. La déclarer « :rw » pour l'autoriser."
        )
    return racine, resolu


def report(racines: Optional[List[Root]] = None) -> Dict[str, object]:
    """
    Décrit les racines déclarées, pour `/health` et pour un agent.

    Un agent doit pouvoir savoir **où** il a le droit de regarder avant d'essayer,
    plutôt que de le découvrir par une série de refus.
    """
    effectives = racines if racines is not None else declared_roots()
    return {
        "variable": VARIABLE,
        "count": len(effectives),
        "writable_count": sum(1 for racine in effectives if racine.writable),
        "roots": [racine.to_dict() for racine in effectives],
    }
