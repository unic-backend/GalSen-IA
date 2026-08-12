"""
Les lecteurs d'écran disponibles, et pourquoi ils ne le sont pas (ch. 05).

Ce module ne devine rien. Il répond à une question — « peut-on regarder l'écran
ici, et comment ? » — et quand la réponse est non, il dit **laquelle** des trois
raisons s'applique :

1. **aucun affichage** : pas de session graphique du tout ;
2. **bibliothèque absente** : la session existe, l'accès n'est pas installé ;
3. **pas encore implémenté** : le backend de cette plateforme reste à écrire, et
   il ne peut pas l'être ici — le vérifier demande une machine avec un bureau,
   comme TEST 2 et TEST 6 en demandent une avec Docker.

Distinguer ces trois-là n'est pas de la politesse. « Aucun élément trouvé »,
« l'outil n'est pas installé » et « personne n'a écrit ce code » conduisent à
trois actions différentes, et les confondre fait chercher au mauvais endroit.

L'ordre de préférence est décidé (ADR-017 §3) : **accessibilité avant pixels**.
Une capture d'écran envoyée à un modèle est ce qu'ADR-014 existe pour refuser, et
des pixels ne portent aucune identité — donc aucune approbation lisible.
"""

import importlib.util
import logging
import os
import platform
from typing import List, Optional

from .interfaces import ScreenBackend, ScreenUnavailable
from .types import ScreenSnapshot

logger = logging.getLogger(__name__)

# Variables qui trahissent une session graphique sur les systèmes de type Unix.
VARIABLES_D_AFFICHAGE = ("DISPLAY", "WAYLAND_DISPLAY")


def session_graphique() -> bool:
    """
    Indique si une session graphique semble exister.

    Sur Windows et macOS l'interface fait partie du système : la question ne se
    pose que sur les systèmes de type Unix, où un serveur sans écran est le cas
    normal — celui de l'image de production de cette plateforme.
    """
    if platform.system() in ("Windows", "Darwin"):
        return True
    return any(os.environ.get(variable) for variable in VARIABLES_D_AFFICHAGE)


class _BackendDePlateforme(ScreenBackend):
    """
    Base des backends liés à un système d'exploitation.

    Chaque sous-classe nomme sa plateforme et le module qui lui donne accès à
    l'arbre d'accessibilité. La disponibilité est calculée ici, une seule fois,
    pour que les trois raisons soient formulées de la même façon partout.
    """

    #: Valeur de `platform.system()` sur laquelle ce backend s'applique.
    systeme: str = ""

    #: Module Python qui donne accès à l'arbre, et comment l'obtenir.
    module: str = ""
    installation: str = ""

    def unavailable_reason(self) -> Optional[str]:
        """Retourne la raison précise, ou None si le backend peut servir."""
        if platform.system() != self.systeme:
            return (
                f"Le backend « {self.name} » vise {self.systeme} ; "
                f"cette machine est un {platform.system()}."
            )
        if not session_graphique():
            return (
                "Aucune session graphique détectée "
                f"({', '.join(VARIABLES_D_AFFICHAGE)} vides) : il n'y a pas d'écran à lire."
            )
        if importlib.util.find_spec(self.module) is None:
            return (
                f"Le module « {self.module} » n'est pas installé. {self.installation}"
            )
        return (
            f"Le backend « {self.name} » n'est pas encore implémenté. Le vérifier "
            "demande une machine avec un bureau ; il est livré dans la phase qui "
            "peut l'exécuter (VOLET 34, ch. 05)."
        )

    def snapshot(self) -> ScreenSnapshot:
        """Refuse, en nommant la raison."""
        raise ScreenUnavailable(self.unavailable_reason())


class AtSpiBackend(_BackendDePlateforme):
    """Arbre d'accessibilité de Linux, via AT-SPI."""

    name = "at-spi"
    family = "accessibility"
    systeme = "Linux"
    module = "pyatspi"
    installation = "Sur Debian ou Ubuntu : « apt install python3-pyatspi »."


class UiaBackend(_BackendDePlateforme):
    """Arbre d'accessibilité de Windows, via UI Automation."""

    name = "uia"
    family = "accessibility"
    systeme = "Windows"
    module = "pywinauto"
    installation = "« pip install pywinauto »."


class AxBackend(_BackendDePlateforme):
    """Arbre d'accessibilité de macOS, via l'API Accessibility."""

    name = "ax"
    family = "accessibility"
    systeme = "Darwin"
    module = "ApplicationServices"
    installation = "« pip install pyobjc-framework-ApplicationServices »."


class PixelBackend(ScreenBackend):
    """
    Repli par capture d'écran.

    Il est **déclaré comme repli**, jamais comme alternative. Deux raisons, et la
    première suffit :

    - une capture envoyée à un modèle est ce qu'ADR-014 refuse, et ADR-018 la
      range parmi les charges qu'aucune dérogation ne couvrira ;
    - des pixels ne portent pas d'identité. Une demande d'approbation qui dit
      « cliquer en (412, 380) » n'est pas évaluable par un humain.

    Il servira là où l'arbre est muet — une application qui ne l'expose pas — et
    ce qu'il rendra devra être présenté comme moins fiable, jamais mélangé
    silencieusement avec ce que l'arbre a donné.
    """

    name = "pixels"
    family = "pixels"

    def unavailable_reason(self) -> Optional[str]:
        """Retourne la raison précise, ou None si la capture est possible."""
        if not session_graphique():
            return (
                "Aucune session graphique détectée : il n'y a pas d'écran à capturer."
            )
        if importlib.util.find_spec("mss") is None:
            return "Le module « mss » n'est pas installé. « pip install mss »."
        return (
            "Le repli par pixels n'est pas encore implémenté. Il vient après un "
            "backend d'accessibilité, jamais avant (ADR-017 §3)."
        )

    def snapshot(self) -> ScreenSnapshot:
        """Refuse, en nommant la raison."""
        raise ScreenUnavailable(self.unavailable_reason())


#: Ordre de préférence : accessibilité d'abord, pixels en dernier.
BACKENDS: List[type] = [AtSpiBackend, UiaBackend, AxBackend, PixelBackend]


def backends_disponibles(candidats: Optional[List[ScreenBackend]] = None) -> List[ScreenBackend]:
    """
    Retourne les backends utilisables, du plus fiable au moins fiable.

    Args:
        candidats: Backends à examiner ; ceux de la plateforme sinon. Sert aux
            tests, qui fournissent un lecteur vérifiable sans bureau.

    Returns:
        Les backends dont `unavailable_reason()` est `None`, accessibilité en tête.
    """
    examines = candidats if candidats is not None else [classe() for classe in BACKENDS]
    utilisables = [backend for backend in examines if backend.available()]
    utilisables.sort(key=lambda backend: 0 if backend.family == "accessibility" else 1)
    return utilisables


def raisons_d_indisponibilite(
    candidats: Optional[List[ScreenBackend]] = None,
) -> List[dict]:
    """
    Retourne, pour chaque backend, ce qui l'empêche de servir.

    C'est ce qu'un opérateur lit pour savoir quoi installer. Un rapport qui dirait
    seulement « indisponible » l'enverrait chercher au hasard.
    """
    examines = candidats if candidats is not None else [classe() for classe in BACKENDS]
    return [
        {
            "backend": backend.name,
            "family": backend.family,
            "available": backend.available(),
            "reason": backend.unavailable_reason(),
        }
        for backend in examines
    ]
