"""
Ce que la plateforme remarque sans qu'on lui demande (découverte proactive).

C'était la dernière capacité absente du brief : *« proactive opportunity
discovery — nothing runs unprompted »*. Tout le reste de la plateforme attend
une requête.

## Le piège de la proactivité, et comment ce module l'évite

Un assistant qui suggère est très facile à écrire et très facile à rendre
insupportable. Trois façons de rater, et la réponse de ce fichier à chacune :

1. **Suggérer ce qu'on n'a pas mesuré.** Chaque observation porte ses
   `evidence` — des valeurs lues dans l'état réel — et un détecteur qui ne peut
   pas mesurer ne dit **rien** plutôt que de supposer. C'est la même règle que
   l'analyste d'opportunités (ch. 11) : *toute affirmation porte sa source, ou
   elle n'est pas faite.*

2. **Répéter.** Une suggestion écartée ne revient pas — sauf si la situation a
   changé, et le changement se constate par une empreinte des preuves
   (`journal.py`). Un assistant qui redemande la même chose chaque heure finit
   ignoré, et c'est alors la suggestion importante qui se perd.

3. **Agir.** Rien ici n'agit. Une observation propose une action et nomme qui
   doit la décider. Ranger un disque ou lancer un entraînement au nom de
   quelqu'un est exactement ce que le portillon (ADR-006) existe pour empêcher.

## Ce qui n'est pas une observation

Un détecteur qui ne trouve rien rend une liste vide, et c'est le cas normal :
la plateforme n'a pas à trouver quelque chose à dire à chaque passage.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Priorités. Trois suffisent : au-delà, personne ne distingue plus les niveaux,
#: et un barème à cinq crans sert surtout à éviter de trancher.
PRIORITES = ("blocking", "worth_doing", "for_information")


@dataclass
class Observation:
    """
    Quelque chose que la plateforme a remarqué, avec de quoi le vérifier.

    Attributes:
        source: Détecteur qui l'a produite.
        finding: Ce qui a été constaté, en une phrase.
        evidence: Les valeurs mesurées qui le soutiennent.
        suggested_action: Ce qu'il y a à faire — jamais fait automatiquement.
        decided_by: Qui doit trancher : `operator` ou `owner`.
        priority: Une des trois valeurs de `PRIORITES`.
    """

    source: str
    finding: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_action: str = ""
    decided_by: str = "operator"
    priority: str = "worth_doing"

    @property
    def id(self) -> str:
        """
        Identifiant stable d'une observation, dérivé de sa source et de son constat.

        Stable veut dire : la même situation produit le même identifiant à
        chaque passage. C'est ce qui permet de l'écarter une fois pour toutes
        plutôt que de la revoir à chaque scan.
        """
        graine = f"{self.source}|{self.finding}"
        return f"obs_{hashlib.sha256(graine.encode('utf-8')).hexdigest()[:12]}"

    @property
    def fingerprint(self) -> str:
        """
        Empreinte des preuves.

        Elle change quand la situation change. Une observation écartée revient
        si son empreinte a bougé : sinon, écarter « 3 fichiers sans test »
        masquerait aussi « 300 fichiers sans test » six mois plus tard.
        """
        graine = repr(sorted(self.evidence.items()))
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'observation, identifiant et empreinte compris."""
        return {
            "id": self.id,
            "fingerprint": self.fingerprint,
            "source": self.source,
            "finding": self.finding,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
            "decided_by": self.decided_by,
            "priority": self.priority,
        }


def observation(
    source: str,
    finding: str,
    evidence: Optional[Dict[str, Any]] = None,
    suggested_action: str = "",
    decided_by: str = "operator",
    priority: str = "worth_doing",
) -> Observation:
    """
    Construit une observation, en refusant celles qui ne prouvent rien.

    Raises:
        ValueError: Sans preuve ou sans action proposée. Une observation sans
            preuve est une opinion, et une observation sans suite est du bruit.
    """
    if not evidence:
        raise ValueError(
            f"Observation « {source} » sans preuve : une suggestion qui ne "
            "renvoie à aucune mesure est une opinion."
        )
    if not suggested_action:
        raise ValueError(
            f"Observation « {source} » sans action proposée : signaler sans "
            "dire quoi faire déplace la charge sur la personne."
        )
    if priority not in PRIORITES:
        raise ValueError(f"Priorité « {priority} » inconnue : {', '.join(PRIORITES)}.")
    return Observation(
        source=source, finding=finding, evidence=evidence,
        suggested_action=suggested_action, decided_by=decided_by, priority=priority,
    )


def sort_observations(observations: List[Observation]) -> List[Observation]:
    """Trie par priorité, du bloquant à l'informatif."""
    rang = {nom: index for index, nom in enumerate(PRIORITES)}
    return sorted(observations, key=lambda o: (rang.get(o.priority, 99), o.source))
