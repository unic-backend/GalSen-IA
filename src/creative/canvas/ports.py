"""
Les ports : ce qu'une arête transporte, et quand elle a le droit d'exister
(K07, ADR-031 décision 2).

## La règle, en une phrase

Une arête est légale **seulement** quand le type du port de sortie est **égal**
à celui du port d'entrée. Pas de conversion implicite, pas de « assez proche »,
pas d'élargissement.

## Pourquoi aussi strict

L'audit K01 a mesuré ce que coûte l'inverse :

```js
const perspective = FOCAL_PERSPECTIVE[focalLength] || "";
```

Une valeur non prévue devient la chaîne vide — sans avertissement, sans trace.
Personne n'apprend jamais que la focale demandée n'a rien produit. Une
conversion implicite entre types de port ferait exactement cela, une couche plus
haut : brancher un `text` sur une entrée `reference` « marcherait », et le
résultat serait une image de quelqu'un d'autre.

## D'où vient le vocabulaire

Aucun type n'est inventé ici. Chacun existe déjà ailleurs dans la plateforme, et
la colonne « défini par » le dit. Un type de port qui n'aurait pas de définition
ailleurs serait un type que rien ne sait produire ni consommer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

#: Les types transportables, avec ce qui les définit déjà dans la plateforme.
TYPES_DE_PORT: Dict[str, str] = {
    "text": "la demande écrite, ou une intention",
    "image": "jobs.GENRES",
    "video": "jobs.GENRES",
    "audio": "jobs.GENRES",
    "analysis": "jobs.GENRES — un rapport, jamais un artefact",
    "reference": "creative/reference/ — une identité, par son identifiant",
    "world": "creative/world.py — un WorldState",
    "direction": "creative/direction.py + cinema.py — un ShotSpec",
    "style": "creative/style.py — une famille de style",
    "voice": "creative/voice/ — une affectation de voix",
    "intent": "creative/intent.py — un CreativeIntent",
}

#: Les motifs de refus d'une arête. Ils sont distincts parce qu'ils ne se
#: corrigent pas de la même façon.
TYPE_INCONNU = "UNKNOWN_PORT_TYPE"
TYPES_DIFFERENTS = "TYPE_MISMATCH"


class PortRefused(ValueError):
    """Un port ou une arête qui ne peut pas exister tel quel."""


@dataclass(frozen=True)
class Port:
    """
    Un point de branchement, entrée ou sortie.

    Attributes:
        name: Le nom du port sur son nœud.
        port_type: Le type transporté, parmi `TYPES_DE_PORT`.
        required: Pour une entrée, si le nœud est inutilisable sans elle. Une
            entrée requise non branchée laisse le nœud `BLOCKED` **en la
            nommant** — elle n'est jamais remplie par un défaut.
    """

    name: str
    port_type: str
    required: bool = True

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise PortRefused("Un port sans nom ne se branche pas.")
        if self.port_type not in TYPES_DE_PORT:
            raise PortRefused(
                f"Type de port « {self.port_type} » non déclaré. Déclarés : "
                f"{sorted(TYPES_DE_PORT)}. Un type sans définition ailleurs "
                "dans la plateforme est un type que rien ne sait produire."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"name": self.name, "port_type": self.port_type,
                "required": self.required}


def edge_is_legal(source: Port, target: Port) -> Dict[str, Any]:
    """
    Dit si une arête peut relier deux ports, et pourquoi pas.

    Args:
        source: Le port de sortie.
        target: Le port d'entrée.

    Returns:
        `legal`, et quand elle ne l'est pas, `refusal` et `reason` nommant
        **les deux** types. Un refus qui ne nomme qu'un côté oblige à deviner
        lequel changer.
    """
    for port in (source, target):
        if port.port_type not in TYPES_DE_PORT:
            return {"legal": False, "refusal": TYPE_INCONNU,
                    "reason": f"Type « {port.port_type} » non déclaré."}
    if source.port_type != target.port_type:
        return {
            "legal": False, "refusal": TYPES_DIFFERENTS,
            "reason": (f"« {source.name} » sort du {source.port_type} et "
                       f"« {target.name} » attend du {target.port_type}. "
                       "Aucune conversion implicite : elle ferait passer une "
                       "valeur pour ce qu'elle n'est pas."),
        }
    return {"legal": True, "refusal": "", "reason": ""}


def port_report() -> Dict[str, Any]:
    """
    Le vocabulaire de ports et la règle de légalité.

    Returns:
        Les types déclarés avec leur définition d'origine, et les règles tenues.
    """
    return {
        "port_types": dict(TYPES_DE_PORT),
        "count": len(TYPES_DE_PORT),
        "refusals": [TYPE_INCONNU, TYPES_DIFFERENTS],
        "rules": [
            "Une arête est légale seulement si les deux types sont égaux.",
            "Aucune conversion implicite, aucun élargissement.",
            "Un refus nomme les deux types, jamais un seul.",
            "Aucun type n'est inventé ici : chacun est défini ailleurs.",
        ],
    }


def declared_types() -> Tuple[str, ...]:
    """Les types de port déclarés, triés."""
    return tuple(sorted(TYPES_DE_PORT))
