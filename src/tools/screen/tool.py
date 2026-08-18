"""
Outil de lecture d'écran (VOLET 34, ch. 05).

ADR-017 tranche la forme : ce qui manquait à la plateforme, ce sont des **mains**,
et des mains sont des outils. Regarder un écran n'est donc pas une nouvelle
architecture d'agent — c'est une entrée de plus au catalogue, qui hérite du
portillon d'approbation, du journal d'audit, du RBAC et de la propriété par sujet
sans qu'on ait à les réécrire.

## Ce que cet outil garantit

- **Il lit, il n'agit pas.** Aucun clic, aucune frappe. Agir est le chapitre 06,
  et le séparer permet de donner la vue à un agent sans lui donner la main.
- **Il rend des éléments identifiés**, pas des pixels : rôle, libellé, bornes.
  C'est ce dont le portillon a besoin pour qu'un humain puisse évaluer ce qu'il
  approuve (ADR-017 §4).
- **Il refuse en nommant la raison.** Sur un serveur sans écran — le cas de
  l'image de production — il dit qu'il n'y a pas d'affichage, pas qu'il n'a rien
  vu.
- **Ce qu'il lit ne part pas chez un tiers.** ADR-014 refuse qu'une donnée quitte
  la plateforme ; ADR-018 range les captures d'écran parmi les charges qu'aucune
  dérogation ne couvrira. `assert_stays_local()` en fait une vérification et non
  une intention.
"""

import logging
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

from .backends import backends_disponibles, raisons_d_indisponibilite
from .interfaces import ScreenBackend, ScreenUnavailable
from .types import ScreenElement, ScreenSnapshot

logger = logging.getLogger(__name__)

# Familles de fournisseurs auxquelles un contenu d'écran ne doit jamais être
# soumis. La liste est nominative plutôt que déduite : un fournisseur ajouté au
# projet doit être classé explicitement, pas hérité d'une règle implicite.
FOURNISSEURS_INTERDITS = (
    "OpenAIProvider", "AnthropicProvider", "GoogleProvider", "HostedProvider",
)


class ScreenCaptureLeavingHost(PermissionError):
    """Une lecture d'écran allait être envoyée hors de la machine."""


def assert_stays_local(provider: Any) -> None:
    """
    Refuse qu'un contenu d'écran parte vers un fournisseur tiers.

    Le refus est **inconditionnel** : il ne consulte pas `GALSEN_SOVEREIGN_MODE`
    et ne consultera aucune dérogation. ADR-018 le formule ainsi parce qu'une
    image de l'écran de quelqu'un est la charge la plus révélatrice que cette
    plateforme manipulera jamais — la ranger derrière un drapeau, c'est accepter
    qu'un jour le drapeau soit mal positionné.

    Args:
        provider: Le fournisseur pressenti pour interpréter la lecture.

    Raises:
        ScreenCaptureLeavingHost: Si le fournisseur est hébergé par un tiers.
    """
    noms = {type(provider).__name__}
    noms.update(base.__name__ for base in type(provider).__mro__)

    interdits = noms & set(FOURNISSEURS_INTERDITS)
    if interdits:
        raise ScreenCaptureLeavingHost(
            f"Refus : une lecture d'écran ne part pas vers « {sorted(interdits)[0]} ». "
            "ADR-018 range les captures d'écran parmi les charges qu'aucune "
            "dérogation ne couvre."
        )


class ScreenTool(BaseTool):
    """Lit l'écran et rend ses éléments, ou dit pourquoi il ne peut pas."""

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 backends: Optional[List[ScreenBackend]] = None) -> None:
        """
        Args:
            config: Configuration de l'outil.
            backends: Lecteurs à utiliser ; ceux de la plateforme sinon.
                Les tests fournissent ici un lecteur vérifiable sans bureau.
        """
        super().__init__(config)
        self._backends = backends

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération de lecture d'écran.

        Args:
            *args: L'opération — `availability`, `snapshot`, `find` — puis ses
                arguments.
            **kwargs: Options de l'opération.

        Returns:
            Le résultat de l'opération.

        Raises:
            ValueError: Opération absente ou inconnue.
            ScreenUnavailable: Aucun lecteur ne peut servir.
        """
        if not args:
            raise ValueError(
                "Une opération est requise. Disponibles : "
                + ", ".join(self.available_operations())
            )

        operation = args[0]
        methode = getattr(self, f"_op_{operation}", None)
        if methode is None:
            raise ValueError(
                f"Opération « {operation} » inconnue. Disponibles : "
                + ", ".join(self.available_operations())
            )
        return methode(*args[1:], **kwargs)

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------

    def _op_availability(self) -> Dict[str, Any]:
        """
        Décrit ce qui peut lire l'écran, et ce qui manque au reste.

        Cette opération répond **toujours**, y compris sur un serveur sans
        écran : c'est elle qui permet à un opérateur de savoir quoi installer,
        et à un agent de constater qu'il est aveugle plutôt que de le déduire
        d'un résultat vide.
        """
        rapport = raisons_d_indisponibilite(self._backends)
        utilisables = [ligne for ligne in rapport if ligne["available"]]
        return {
            "can_see": bool(utilisables),
            "preferred": utilisables[0]["backend"] if utilisables else None,
            "backends": rapport,
        }

    def _op_snapshot(self) -> Dict[str, Any]:
        """
        Lit l'écran avec le lecteur le plus fiable disponible.

        Raises:
            ScreenUnavailable: Aucun lecteur ne peut servir ; le message nomme
                ce qui manque pour chacun.
        """
        return self._instantane().to_dict()

    def _op_find(self, requete: str, role: Optional[str] = None) -> Dict[str, Any]:
        """
        Cherche des éléments par libellé, et éventuellement par rôle.

        Args:
            requete: Fragment de libellé cherché, insensible à la casse.
            role: Rôle d'accessibilité exigé, s'il y en a un.

        Returns:
            Les éléments correspondants, décrits comme le portillon les lira.
        """
        if not isinstance(requete, str) or not requete.strip():
            raise ValueError("Une requête non vide est requise.")

        aiguille = requete.strip().lower()
        instantane = self._instantane()
        trouves = [
            element for element in instantane.elements
            if aiguille in element.label.lower()
            and (role is None or element.role == role)
        ]
        return {
            "backend": instantane.backend,
            "query": requete,
            "match_count": len(trouves),
            "elements": [element.to_dict() for element in trouves],
        }

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _instantane(self) -> ScreenSnapshot:
        """Lit l'écran, ou refuse en expliquant chaque indisponibilité."""
        utilisables = backends_disponibles(self._backends)
        if not utilisables:
            details = "; ".join(
                f"{ligne['backend']} : {ligne['reason']}"
                for ligne in raisons_d_indisponibilite(self._backends)
            )
            raise ScreenUnavailable(f"Aucun lecteur d'écran disponible. {details}")

        backend = utilisables[0]
        instantane = backend.snapshot()
        if not instantane.backend:
            instantane.backend = backend.name
        if backend.family == "pixels":
            # Le repli doit se voir dans le résultat, pas seulement dans les
            # journaux : un appelant qui mélangerait les deux fiabilités
            # traiterait une déduction comme une lecture.
            instantane.notes.append(
                "Lu par repli en pixels : les éléments n'ont pas d'identité "
                "fournie par le système, seulement une position."
            )
        return instantane


__all__ = [
    "FOURNISSEURS_INTERDITS",
    "ScreenCaptureLeavingHost",
    "ScreenElement",
    "ScreenSnapshot",
    "ScreenTool",
    "ScreenUnavailable",
    "assert_stays_local",
]
