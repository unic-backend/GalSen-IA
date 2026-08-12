"""
Ce qui a déjà été dit, et ce que quelqu'un a écarté.

Le vrai problème d'un assistant proactif n'est pas de trouver quelque chose à
dire : c'est de **se taire**. Une suggestion répétée à chaque passage est
ignorée en une semaine, et c'est alors la suggestion importante qui se perd avec
les autres.

## La règle, et sa nuance

Une observation écartée ne revient pas — **sauf si la situation a changé**.

Le changement se constate par l'empreinte des preuves
(`Observation.fingerprint`), pas par le temps qui passe. Écarter « 3 fichiers
sans test » ne doit pas masquer « 300 fichiers sans test » six mois plus tard :
c'est le même constat, ce n'est pas la même situation. À l'inverse, ramener la
même ligne inchangée parce qu'un délai a expiré est exactement le harcèlement
que ce fichier existe pour éviter.

## Où c'est écrit

Un fichier `jsonl` dans le répertoire de données, ajouté en continu, dont la
dernière ligne d'un identifiant fait foi — la même forme que le journal des
opérations de fichiers (ch. 07). Rien n'y est effacé : savoir qu'une suggestion
a été écartée trois fois est une information sur la suggestion.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FICHIER = "proactive_journal.jsonl"


class SuggestionJournal:
    """
    Retient ce qui a été montré et ce qui a été écarté.

    Exemple:
        journal = SuggestionJournal()
        journal.dismiss(observation)          # ne plus me le dire
        journal.is_dismissed(observation)     # vrai tant que rien n'a changé
    """

    def __init__(self, path: Optional[str] = None) -> None:
        """
        Args:
            path: Fichier journal ; `GALSEN_DATA_DIR/proactive_journal.jsonl` sinon.
        """
        from src.storage.paths import data_dir

        self.path = path or os.path.join(data_dir(), FICHIER)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def dismiss(self, observation, by: str = "operator", reason: str = "") -> None:
        """
        Écarte une observation : elle ne sera plus montrée en l'état.

        Args:
            observation: Observation écartée.
            by: Qui a écarté.
            reason: Pourquoi, si la personne l'a dit.
        """
        self._inscrire({
            "id": observation.id,
            "fingerprint": observation.fingerprint,
            "event": "dismissed",
            "by": by,
            "reason": reason,
            "at": time.time(),
            # Le constat est conservé : relire un journal d'identifiants seuls
            # ne dit pas ce qui a été écarté.
            "finding": observation.finding,
        })

    def record_surfaced(self, observations: List[Any]) -> None:
        """Note que des observations ont été montrées."""
        instant = time.time()
        for observation in observations:
            self._inscrire({
                "id": observation.id,
                "fingerprint": observation.fingerprint,
                "event": "surfaced",
                "at": instant,
                "finding": observation.finding,
            })

    def _inscrire(self, entree: Dict[str, Any]) -> None:
        """Ajoute une ligne au journal ; un échec d'écriture ne casse pas le scan."""
        try:
            with open(self.path, "a", encoding="utf-8") as fichier:
                fichier.write(json.dumps(entree, ensure_ascii=False) + "\n")
        except OSError as erreur:
            logger.warning("Journal proactif non écrit : %s", erreur)

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def _entrees(self) -> List[Dict[str, Any]]:
        """Lit le journal ; un fichier illisible vaut un journal vide, en le disant."""
        if not os.path.isfile(self.path):
            return []
        entrees = []
        try:
            with open(self.path, "r", encoding="utf-8") as fichier:
                for ligne in fichier:
                    ligne = ligne.strip()
                    if not ligne:
                        continue
                    try:
                        entrees.append(json.loads(ligne))
                    except ValueError:
                        # Une ligne corrompue n'emporte pas les autres : le
                        # journal est ajouté en continu, une écriture a pu être
                        # coupée.
                        logger.warning("Ligne illisible dans le journal proactif.")
        except OSError as erreur:
            logger.warning("Journal proactif illisible : %s", erreur)
        return entrees

    def dismissals(self) -> Dict[str, str]:
        """
        Retourne, par identifiant, l'empreinte au moment où il a été écarté.

        La dernière décision fait foi : quelqu'un peut écarter, puis reconsidérer.
        """
        derniers: Dict[str, str] = {}
        for entree in self._entrees():
            if entree.get("event") == "dismissed":
                derniers[entree["id"]] = entree.get("fingerprint", "")
        return derniers

    def is_dismissed(self, observation) -> bool:
        """
        Indique si une observation a été écartée **et n'a pas changé depuis**.

        C'est la nuance qui distingue « se taire » de « cacher ».
        """
        empreinte = self.dismissals().get(observation.id)
        return empreinte is not None and empreinte == observation.fingerprint

    def filter(self, observations: List[Any]) -> List[Any]:
        """Retire les observations écartées dont la situation n'a pas bougé."""
        ecartees = self.dismissals()
        return [
            observation for observation in observations
            if ecartees.get(observation.id) != observation.fingerprint
        ]

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retourne les dernières entrées, de la plus récente à la plus ancienne."""
        return sorted(self._entrees(), key=lambda e: e.get("at", 0), reverse=True)[:limit]
