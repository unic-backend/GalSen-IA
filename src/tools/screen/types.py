"""
Ce qu'un écran rend quand on le regarde (VOLET 34, ch. 05).

La forme de ces types porte la décision d'ADR-017 §4 : **une action doit pouvoir
nommer sa cible**. Le portillon d'approbation ne peut pas demander à un humain
d'approuver « cliquer en (412, 380) » — une approbation qu'on ne peut pas évaluer
est un tampon accompagné d'une ligne de journal.

Un élément porte donc son identité — rôle, libellé, bornes — et pas seulement sa
position. C'est l'argument pour l'arbre d'accessibilité qu'aucun benchmark ne
fait, et il vient de notre propre architecture.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScreenElement:
    """
    Un élément d'interface, tel que le système d'exploitation le décrit.

    Attributes:
        role: Rôle d'accessibilité — `button`, `text`, `menu item`…
        label: Texte lisible par un humain, celui qu'un lecteur d'écran annonce.
        bounds: `(x, y, largeur, hauteur)` en pixels, pour agir dessus.
        identifier: Identifiant stable donné par l'application, s'il existe.
        enabled: L'élément accepte-t-il une interaction.
        focused: L'élément a-t-il le focus clavier.
        application: Nom de l'application propriétaire.
    """

    role: str
    label: str = ""
    bounds: Optional[Tuple[int, int, int, int]] = None
    identifier: Optional[str] = None
    enabled: bool = True
    focused: bool = False
    application: str = ""

    def describe(self) -> str:
        """
        Décrit l'élément en une ligne, pour une demande d'approbation.

        C'est ce qu'un humain lira avant d'autoriser une action. Un élément sans
        libellé ni identifiant se décrit par son rôle et sa position — et ce cas
        doit rester visible plutôt que d'être rempli par une invention.
        """
        morceaux = [self.role]
        if self.label:
            morceaux.append(f"« {self.label} »")
        elif self.identifier:
            morceaux.append(f"[{self.identifier}]")
        else:
            morceaux.append("sans libellé")
        if self.application:
            morceaux.append(f"dans {self.application}")
        if not self.enabled:
            morceaux.append("(désactivé)")
        return " ".join(morceaux)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'élément."""
        return {
            "role": self.role,
            "label": self.label,
            "bounds": list(self.bounds) if self.bounds else None,
            "identifier": self.identifier,
            "enabled": self.enabled,
            "focused": self.focused,
            "application": self.application,
            "description": self.describe(),
        }


@dataclass
class ScreenSnapshot:
    """
    Ce qui a été lu de l'écran, et **par quoi**.

    `backend` n'est pas décoratif : un instantané lu dans l'arbre
    d'accessibilité et un instantané déduit de pixels n'ont pas la même
    fiabilité, et l'appelant doit pouvoir en tenir compte — comme la recherche
    dit déjà si elle a été sémantique ou lexicale (ADR-015).
    """

    elements: List[ScreenElement] = field(default_factory=list)
    backend: str = ""
    captured_at: float = field(default_factory=time.time)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'instantané, éléments compris."""
        return {
            "backend": self.backend,
            "captured_at": self.captured_at,
            "element_count": len(self.elements),
            "elements": [element.to_dict() for element in self.elements],
            "notes": self.notes,
        }
