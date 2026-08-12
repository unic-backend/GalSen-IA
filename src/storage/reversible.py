"""
Des opérations de fichiers qu'on peut défaire (VOLET 34, ch. 07).

Le brief demande d'« organiser, renommer, déplacer, archiver ». Ces quatre-là ont
une propriété commune que la lecture n'a pas : **quand l'agent se trompe, le
travail de quelqu'un a bougé**. Et le moment où on s'en aperçoit est rarement
celui où l'on peut encore reconstituer l'état d'avant.

Ce module rend chaque opération réversible, et enregistre de quoi la défaire.

## Trois décisions, et la dernière est la plus importante

**Rien n'est supprimé.** `remove()` déplace vers une quarantaine à l'intérieur de
la même racine. Une suppression qu'un agent décide et qu'un humain découvre trois
jours plus tard doit pouvoir se défaire ; `os.remove` ne le permet pas, et aucun
degré de prudence dans le code appelant ne rattrape cela.

**Le journal précède l'acte.** L'entrée est écrite avant que le fichier bouge.
L'ordre inverse laisserait une fenêtre où un déplacement a eu lieu sans que rien
ne sache le défaire — le même raisonnement que pour les octets écrits avant
l'index (ADR-016).

**Une opération ne s'annule qu'une fois.** Rejouer une annulation écraserait un
état plus récent avec un état ancien, ce qui est une deuxième perte déguisée en
réparation.
"""

import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .roots import Root, RootRefused, resolve

logger = logging.getLogger(__name__)

#: Répertoire de quarantaine, créé à la racine concernée.
QUARANTAINE = ".galsen-corbeille"

#: Nom du journal, dans le répertoire de données.
JOURNAL = "file_operations.jsonl"


class OperationRefused(PermissionError):
    """L'opération n'est pas permise : hors racine, racine en lecture seule, cible absente."""


class UndoRefused(RuntimeError):
    """L'annulation n'est pas possible, et la raison accompagne toujours l'exception."""


@dataclass
class FileOperation:
    """
    Une opération enregistrée, avec de quoi la défaire.

    Attributes:
        kind: `move`, `rename`, `remove` ou `archive`.
        source: Chemin d'origine, absolu.
        destination: Où le contenu se trouve après l'opération.
        root: Nom de la racine concernée.
        reason: Pourquoi l'agent l'a faite — ce qu'un humain lira.
        undone: L'opération a-t-elle déjà été annulée.
    """

    kind: str
    source: str
    destination: str
    root: str
    reason: str = ""
    id: str = field(default_factory=lambda: f"op_{uuid.uuid4().hex[:12]}")
    at: float = field(default_factory=time.time)
    undone: bool = False

    def describe(self) -> str:
        """Décrit l'opération en une ligne, pour un humain."""
        verbe = {
            "move": "déplacé", "rename": "renommé",
            "remove": "mis en quarantaine", "archive": "archivé",
        }.get(self.kind, self.kind)
        return f"{os.path.basename(self.source)} {verbe} vers {self.destination}"

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'opération."""
        return {
            "id": self.id, "kind": self.kind, "source": self.source,
            "destination": self.destination, "root": self.root,
            "reason": self.reason, "at": self.at, "undone": self.undone,
            "description": self.describe(),
        }

    @classmethod
    def from_dict(cls, donnees: Dict[str, Any]) -> "FileOperation":
        """Reconstruit une opération depuis le journal."""
        return cls(
            id=donnees["id"], kind=donnees["kind"], source=donnees["source"],
            destination=donnees["destination"], root=donnees["root"],
            reason=donnees.get("reason", ""), at=donnees["at"],
            undone=donnees.get("undone", False),
        )


class ReversibleFiles:
    """
    Déplace, renomme, met en quarantaine et archive — en gardant de quoi défaire.

    Exemple:
        fichiers = ReversibleFiles(racines)
        operation = fichiers.move("projets/vieux.txt", "projets/archive/vieux.txt",
                                  raison="rangement trimestriel")
        fichiers.undo(operation.id)   # le fichier revient
    """

    def __init__(self, racines: List[Root], journal: Optional[str] = None) -> None:
        """
        Args:
            racines: Racines déclarées (`src/storage/roots.py`).
            journal: Fichier journal ; `GALSEN_DATA_DIR/file_operations.jsonl` sinon.
        """
        from .paths import data_dir

        self._racines = racines
        self._journal = journal or os.path.join(data_dir(), JOURNAL)
        os.makedirs(os.path.dirname(os.path.abspath(self._journal)), exist_ok=True)

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------

    def move(self, source: str, destination: str, raison: str = "") -> FileOperation:
        """
        Déplace un fichier ou un répertoire.

        Args:
            source: Chemin d'origine, dans une racine inscriptible.
            destination: Chemin visé, dans une racine inscriptible.
            raison: Pourquoi ; inscrite au journal pour l'humain qui relira.

        Raises:
            OperationRefused: Source absente, hors racine, ou destination occupée.
        """
        return self._deplacer("move", source, destination, raison)

    def rename(self, source: str, nouveau_nom: str, raison: str = "") -> FileOperation:
        """
        Renomme un fichier sans le sortir de son répertoire.

        Args:
            source: Chemin d'origine.
            nouveau_nom: Nom seul, sans séparateur — renommer n'est pas déplacer,
                et confondre les deux ferait traverser une racine par accident.
        """
        if os.sep in nouveau_nom or "/" in nouveau_nom:
            raise OperationRefused(
                f"« {nouveau_nom} » contient un séparateur : renommer ne déplace "
                "pas. Utiliser `move` pour changer de répertoire."
            )
        _, absolu = resolve(source, self._racines, pour_ecriture=True)
        cible = os.path.join(os.path.dirname(absolu), nouveau_nom)
        return self._deplacer("rename", source, cible, raison)

    def remove(self, source: str, raison: str = "") -> FileOperation:
        """
        Met un fichier en quarantaine — **il n'est pas supprimé**.

        La quarantaine vit dans la racine du fichier, ce qui garde l'opération
        sur le même volume : un déplacement y est atomique, et la corbeille ne
        traverse jamais une frontière de racine.
        """
        racine, absolu = resolve(source, self._racines, pour_ecriture=True)
        if not os.path.exists(absolu):
            raise OperationRefused(f"« {source} » n'existe pas : rien à retirer.")

        corbeille = os.path.join(racine.path, QUARANTAINE)
        os.makedirs(corbeille, exist_ok=True)
        cible = os.path.join(corbeille, f"{int(time.time())}_{os.path.basename(absolu)}")
        return self._deplacer("remove", source, cible, raison, deja_resolu=absolu)

    def archive(self, source: str, raison: str = "") -> FileOperation:
        """
        Archive un répertoire en `.zip`, **sans supprimer l'original**.

        L'archive et la source coexistent : « archiver » et « supprimer après
        avoir archivé » sont deux décisions, et les fondre en une seule ferait
        disparaître des données au premier échec de compression.
        """
        racine, absolu = resolve(source, self._racines, pour_ecriture=True)
        if not os.path.isdir(absolu):
            raise OperationRefused(f"« {source} » n'est pas un répertoire : rien à archiver.")

        cible = f"{absolu}.zip"
        if os.path.exists(cible):
            raise OperationRefused(f"« {cible} » existe déjà : rien n'est écrasé.")

        operation = FileOperation(
            kind="archive", source=absolu, destination=cible,
            root=racine.name, reason=raison,
        )
        self._inscrire(operation)
        shutil.make_archive(absolu, "zip", absolu)
        return operation

    # ------------------------------------------------------------------
    # Défaire
    # ------------------------------------------------------------------

    def undo(self, operation_id: str) -> FileOperation:
        """
        Annule une opération enregistrée.

        Args:
            operation_id: Identifiant rendu par l'opération.

        Raises:
            UndoRefused: Opération inconnue, déjà annulée, ou état d'arrivée
                introuvable — dans ce dernier cas quelque chose a bougé depuis,
                et écraser à l'aveugle serait une seconde perte.
        """
        operations = {op.id: op for op in self.history()}
        operation = operations.get(operation_id)
        if operation is None:
            raise UndoRefused(f"Opération « {operation_id} » inconnue du journal.")
        if operation.undone:
            raise UndoRefused(
                f"Opération « {operation_id} » déjà annulée : rejouer une "
                "annulation écraserait un état plus récent."
            )

        if operation.kind == "archive":
            if os.path.exists(operation.destination):
                os.remove(operation.destination)
        else:
            if not os.path.exists(operation.destination):
                raise UndoRefused(
                    f"« {operation.destination} » est introuvable : quelque chose "
                    "a bougé depuis, et l'annulation écraserait à l'aveugle."
                )
            if os.path.exists(operation.source):
                raise UndoRefused(
                    f"« {operation.source} » existe de nouveau : annuler "
                    "l'écraserait."
                )
            os.makedirs(os.path.dirname(operation.source), exist_ok=True)
            shutil.move(operation.destination, operation.source)

        operation.undone = True
        self._inscrire(operation, annulation=True)
        return operation

    def history(self, limit: int = 100) -> List[FileOperation]:
        """
        Retourne les opérations enregistrées, de la plus récente à la plus ancienne.

        Une opération annulée apparaît une seule fois, avec `undone` à vrai : le
        journal est ajouté en continu, et la dernière ligne d'un identifiant fait
        foi.
        """
        if not os.path.isfile(self._journal):
            return []

        par_identifiant: Dict[str, FileOperation] = {}
        with open(self._journal, "r", encoding="utf-8") as fichier:
            for ligne in fichier:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    operation = FileOperation.from_dict(json.loads(ligne))
                except (ValueError, KeyError):
                    # Une ligne illisible est signalée, pas devinée : reconstruire
                    # une opération approximative ferait annuler autre chose.
                    logger.error("Ligne de journal illisible, ignorée : %s", ligne[:80])
                    continue
                par_identifiant[operation.id] = operation

        return sorted(par_identifiant.values(), key=lambda op: op.at, reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _deplacer(self, kind: str, source: str, destination: str, raison: str,
                  deja_resolu: Optional[str] = None) -> FileOperation:
        """Déplace après contrôle, en inscrivant l'opération avant de bouger."""
        racine, absolu = (
            (self._racine_de(deja_resolu), deja_resolu) if deja_resolu
            else resolve(source, self._racines, pour_ecriture=True)
        )
        if not os.path.exists(absolu):
            raise OperationRefused(f"« {source} » n'existe pas.")

        if deja_resolu:
            cible = destination
        else:
            _, cible = resolve(destination, self._racines, pour_ecriture=True)
        if os.path.exists(cible):
            raise OperationRefused(
                f"« {cible} » existe déjà : rien n'est écrasé. Choisir un autre nom."
            )

        operation = FileOperation(
            kind=kind, source=absolu, destination=cible,
            root=racine.name, reason=raison,
        )
        # Le journal précède l'acte : l'ordre inverse laisserait une fenêtre où
        # un fichier a bougé sans que rien ne sache le défaire.
        self._inscrire(operation)
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        shutil.move(absolu, cible)
        return operation

    def _racine_de(self, absolu: str) -> Root:
        """Retrouve la racine qui contient un chemin déjà résolu."""
        for racine in self._racines:
            if absolu.startswith(racine.path + os.sep):
                return racine
        raise RootRefused(f"« {absolu} » est hors des racines déclarées.")

    def _inscrire(self, operation: FileOperation, annulation: bool = False) -> None:
        """Ajoute une ligne au journal."""
        with open(self._journal, "a", encoding="utf-8") as fichier:
            fichier.write(json.dumps(operation.to_dict(), ensure_ascii=False) + "\n")
            fichier.flush()
            os.fsync(fichier.fileno())
        logger.info(
            "%s : %s", "annulation" if annulation else "opération", operation.describe()
        )
