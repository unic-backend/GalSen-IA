"""
Découverte proactive : ce que la plateforme remarque sans qu'on demande.

Dernière capacité absente du brief. Trois règles la tiennent :

1. **Rien n'est suggéré sans preuve mesurée** — un détecteur qui ne peut pas
   mesurer se tait plutôt que de supposer.
2. **Rien n'est répété** — une observation écartée ne revient que si la
   situation a changé, ce qui se constate par l'empreinte de ses preuves.
3. **Rien n'est exécuté** — une observation propose et nomme qui doit décider.
"""

from .journal import SuggestionJournal
from .observations import Observation, observation
from .scan import CADENCE_SECONDES, dismiss, due, scan

__all__ = [
    "CADENCE_SECONDES",
    "Observation",
    "SuggestionJournal",
    "dismiss",
    "due",
    "observation",
    "scan",
]
