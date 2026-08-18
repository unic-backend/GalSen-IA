"""
Every autonomous action, written down before it is forgotten.

A repair that nobody can reconstruct afterwards is a repair nobody can trust.
The journal exists so that the question asked a week later — *what did it change,
why did it think that, and what did it check before merging?* — has an answer
that does not depend on anyone's memory.

Three properties make it worth keeping:

- **It is written as things happen, not at the end.** A run that dies mid-repair
  is exactly the run whose trace matters, and a journal assembled at the end
  would have nothing to say about it.
- **It carries hashes, not promises.** "The file was unchanged" is an assertion;
  a before-and-after SHA-256 is evidence.
- **It never carries a secret.** Redaction reuses `src/security/redaction.py`
  rather than re-deciding what a secret looks like — two lists would disagree,
  and the day they disagree is the day one of them leaks.

The journal records. It never judges, never blocks, and never repairs: a
component that both acts and writes its own verdict is a component that can be
wrong twice in the same direction.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...security.redaction import redact_mapping
from ..tools.workspace import repo_root

#: Les actions consignées. Fermée volontairement : une action qui n'est pas dans
#: cette liste n'a pas été pensée, et l'inventer au vol donnerait un journal où
#: chaque appelant nomme la même chose différemment.
ACTIONS = (
    "read", "write", "command", "patch", "test", "branch",
    "merge", "rollback", "failure", "policy", "diagnosis",
)

#: Entrées conservées en mémoire. Au-delà, les plus anciennes sortent — mais les
#: compteurs, eux, ne sont jamais oubliés (voir `journal_report`).
ENTREES_CONSERVEES = 2000

#: Où le journal persiste, sous la racine des données. Le fichier est ouvert en
#: ajout : une réparation qui meurt en route laisse quand même sa trace.
FICHIER_PAR_DEFAUT = os.path.join("data", "agent-audit", "journal.jsonl")


@dataclass
class AuditEntry:
    """
    Une action autonome, telle qu'elle s'est produite.

    Attributes:
        timestamp: Quand, en secondes depuis l'époque.
        action: L'une de `ACTIONS`.
        actor: Qui agit — le harnais, un agent nommé, la CLI.
        incident_id: L'incident auquel cette action se rattache.
        target: Ce sur quoi elle porte : un chemin, une commande, une branche.
        result: `ok`, `refused`, `failed`, ou un état plus précis.
        detail: Ce qui s'est passé, en clair.
        hashes: Empreintes avant/après, quand il y en a.
    """

    timestamp: float
    action: str
    actor: str
    incident_id: str = ""
    target: str = ""
    result: str = "ok"
    detail: str = ""
    hashes: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, déjà expurgée."""
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "incident_id": self.incident_id,
            "target": self.target,
            "result": self.result,
            "detail": self.detail,
            "hashes": dict(self.hashes),
        }


class AuditJournal:
    """
    Le journal des actions autonomes : en mémoire, et sur disque.

    Thread-safe. L'écriture disque est **facultative** et ne fait jamais tomber
    l'action qu'elle observe : un journal qui casse la réparation qu'il regarde
    serait pire que pas de journal du tout.
    """

    def __init__(self, path: Optional[str] = None, persist: bool = True) -> None:
        """
        Args:
            path: Le fichier `.jsonl`. Celui du dépôt par défaut.
            persist: Écrire sur disque. Les tests le coupent.
        """
        self._verrou = threading.RLock()
        self._entrees: List[AuditEntry] = []
        self._compteurs: Dict[str, int] = {}
        self._oubliees = 0
        self._persist = persist
        self._chemin = path or os.path.join(repo_root(), FICHIER_PAR_DEFAUT)

    # ------------------------------------------------------------------
    # Écrire
    # ------------------------------------------------------------------

    def record(
        self,
        action: str,
        actor: str = "self-healer",
        incident_id: str = "",
        target: str = "",
        result: str = "ok",
        detail: str = "",
        hashes: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Consigne une action.

        Args:
            action: L'une de `ACTIONS`.
            actor: Qui agit.
            incident_id: L'incident concerné.
            target: Le chemin, la commande ou la branche.
            result: L'issue.
            detail: Ce qui s'est passé.
            hashes: Empreintes avant/après.
            metadata: Contexte additionnel — **expurgé** avant d'entrer.

        Returns:
            L'entrée consignée.

        Raises:
            ValueError: Si l'action n'est pas déclarée. Inventer un nom au vol
                donnerait un journal où chacun nomme la même chose autrement.
        """
        if action not in ACTIONS:
            raise ValueError(
                f"Action « {action} » non déclarée. Les actions consignées sont "
                f"{', '.join(ACTIONS)} : une action inventée au vol rendrait le "
                "journal illisible."
            )

        texte = str(detail or "")
        if metadata:
            # `redact_mapping` est le seul juge de ce qu'est un secret. Une
            # seconde liste ici finirait par diverger, et le jour de la
            # divergence est le jour de la fuite.
            texte = f"{texte} | {json.dumps(redact_mapping(metadata), ensure_ascii=False)}"

        entree = AuditEntry(
            timestamp=time.time(), action=action, actor=str(actor),
            incident_id=str(incident_id), target=str(target)[:500],
            result=str(result), detail=texte[:2000], hashes=dict(hashes or {}),
        )

        with self._verrou:
            self._entrees.append(entree)
            self._compteurs[action] = self._compteurs.get(action, 0) + 1
            if len(self._entrees) > ENTREES_CONSERVEES:
                self._entrees.pop(0)
                self._oubliees += 1

        self._ecrire(entree)
        return entree

    def _ecrire(self, entree: AuditEntry) -> None:
        """
        Ajoute une ligne au fichier, sans jamais faire tomber l'appelant.

        Le fichier est ouvert **en ajout** à chaque entrée : une réparation qui
        meurt en route laisse ainsi tout ce qui la précédait.
        """
        if not self._persist:
            return
        try:
            os.makedirs(os.path.dirname(self._chemin), exist_ok=True)
            with open(self._chemin, "a", encoding="utf-8") as fichier:
                fichier.write(json.dumps(entree.as_dict(), ensure_ascii=False) + "\n")
        except OSError:
            # Un journal qui casse la réparation qu'il observe serait pire que
            # pas de journal : l'échec d'écriture est absorbé, et `journal_report`
            # dit que la persistance est indisponible.
            self._persist = False

    # ------------------------------------------------------------------
    # Lire
    # ------------------------------------------------------------------

    def entries(
        self, incident_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Les dernières entrées, éventuellement filtrées par incident.

        Args:
            incident_id: L'incident cherché.
            limit: Nombre maximal d'entrées, de la plus récente à la plus
                ancienne.

        Returns:
            Les entrées, sérialisées.
        """
        with self._verrou:
            trouvees = [
                entree for entree in reversed(self._entrees)
                if incident_id is None or entree.incident_id == incident_id
            ]
        return [entree.as_dict() for entree in trouvees[: max(1, int(limit))]]

    def incidents(self) -> List[str]:
        """Les incidents ayant laissé au moins une trace."""
        with self._verrou:
            return sorted({e.incident_id for e in self._entrees if e.incident_id})

    def journal_report(self) -> Dict[str, Any]:
        """
        Ce que le journal contient, et ce qu'il a oublié.

        Returns:
            Les compteurs par action — qui **survivent** à l'oubli des entrées,
            sans quoi un dépôt actif finirait par dire « aucune réparation ».
        """
        with self._verrou:
            return {
                "entries": len(self._entrees),
                "forgotten": self._oubliees,
                "kept": ENTREES_CONSERVEES,
                "by_action": dict(sorted(self._compteurs.items())),
                "incidents": len({e.incident_id for e in self._entrees if e.incident_id}),
                "persisted_to": self._chemin if self._persist else None,
                "rules": [
                    "Écrit au fil de l'action : une exécution qui meurt en route "
                    "est justement celle dont la trace compte.",
                    "Les empreintes remplacent les promesses : « le fichier n'a "
                    "pas changé » est une affirmation, un SHA-256 est une preuve.",
                    "Aucun secret n'entre : l'expurgation est celle de "
                    "`src/security/redaction.py`, jamais une seconde liste.",
                    "Le journal consigne ; il ne juge pas et ne répare pas.",
                ],
            }
