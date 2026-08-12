"""
L'état de travail partagé d'une requête (VOLET 29, ch. 02).

Ce que les agents partageaient jusqu'ici : `previous_results`, la liste ordonnée
de ce que chacun a **fini** par produire. C'est un compte rendu, pas un espace de
travail. Il ne permet ni de poser une question à un agent qui n'a pas encore
tourné, ni de déposer une observation en cours de route, ni de savoir qui a déjà
répondu à quoi.

Le tableau noir comble exactement cela, et rien de plus :

- **On y publie sous un sujet**, avec l'agent émetteur et, si on veut, un
  destinataire. Un agent lit ce qui le concerne sans avoir à deviner la position
  d'un résultat dans une liste.
- **Il est partagé par tout le contexte d'une requête**, y compris les contextes
  dérivés — c'est la même instance, pas une copie. Une copie ferait deux vérités,
  et ce dépôt en a déjà trouvé trois.
- **Il ne survit pas à la requête.** Ce qui doit durer va en mémoire (VOLET 07),
  qui a un cycle de vie, une rétention et une isolation par sujet. Confondre les
  deux ferait du tableau noir une base de données sans règles.

Un tableau noir n'est pas un canal de discussion libre : il est borné, pour que
la trace d'une requête reste lisible et que deux agents ne s'écrivent pas mille
messages à la seconde.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Au-delà, on n'a plus un état de travail mais un journal — et le journal
# existe déjà, c'est l'audit.
MAX_ENTREES = 200


@dataclass
class Note:
    """Une observation déposée par un agent."""

    topic: str
    value: Any
    author: str
    to: Optional[str] = None
    at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la note pour un rapport ou une trace."""
        donnees = {"topic": self.topic, "value": self.value, "author": self.author}
        if self.to:
            donnees["to"] = self.to
        return donnees


class Blackboard:
    """
    Espace de travail partagé par les agents d'une même requête.

    Exemple:
        tableau.post("sol", {"ph": 6.2}, author="researcher", to="coder")
        tableau.read("sol", pour="coder")
    """

    def __init__(self, max_entries: int = MAX_ENTREES):
        """
        Args:
            max_entries: Nombre maximal de notes conservées. Au-delà, les plus
                anciennes sont oubliées — un état de travail qui grossit sans
                fin n'est plus un état de travail.
        """
        self._notes: List[Note] = []
        self._max = max_entries
        self._lock = threading.RLock()

    def post(self, topic: str, value: Any, author: str, to: Optional[str] = None) -> Note:
        """
        Dépose une observation.

        Args:
            topic: Sujet sous lequel ranger l'observation.
            value: Contenu de l'observation.
            author: Agent qui la dépose.
            to: Destinataire, si elle s'adresse à un agent en particulier.

        Returns:
            La note déposée.
        """
        note = Note(topic=topic, value=value, author=author, to=to)
        with self._lock:
            self._notes.append(note)
            if len(self._notes) > self._max:
                # On oublie par le début : les observations récentes décrivent
                # l'état courant, les anciennes décrivent un état dépassé.
                del self._notes[: len(self._notes) - self._max]
        return note

    def read(self, topic: Optional[str] = None, pour: Optional[str] = None) -> List[Note]:
        """
        Lit les observations, filtrées par sujet et par destinataire.

        Args:
            topic: Sujet recherché ; tous les sujets si None.
            pour: Agent lecteur. Il reçoit les notes qui lui sont adressées **et**
                celles qui ne le sont à personne. Les notes adressées à un autre
                agent ne lui sont pas rendues : sinon « adresser » ne voudrait
                rien dire.

        Returns:
            Les notes correspondantes, de la plus ancienne à la plus récente.
        """
        with self._lock:
            notes = list(self._notes)
        if topic is not None:
            notes = [note for note in notes if note.topic == topic]
        if pour is not None:
            notes = [note for note in notes if note.to in (None, pour)]
        return notes

    def latest(self, topic: str, pour: Optional[str] = None) -> Optional[Note]:
        """Retourne la dernière observation d'un sujet, ou None."""
        notes = self.read(topic, pour=pour)
        return notes[-1] if notes else None

    def topics(self) -> List[str]:
        """Retourne les sujets présents, dans l'ordre d'apparition."""
        with self._lock:
            vus = []
            for note in self._notes:
                if note.topic not in vus:
                    vus.append(note.topic)
        return vus

    def snapshot(self) -> List[Dict[str, Any]]:
        """Retourne l'état complet, sérialisable — pour la trace d'une requête."""
        with self._lock:
            return [note.to_dict() for note in self._notes]

    def __len__(self) -> int:
        """Nombre de notes conservées."""
        with self._lock:
            return len(self._notes)
