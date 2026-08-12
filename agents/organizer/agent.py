"""
File Organizer Agent for GalSen IA (VOLET 34, ch. 11).

The brief asks for an agent that organises, renames, moves and archives files.
Chapter 07 already built the machinery — declared roots, and operations that can
be undone. What was missing is the part that **decides**, and the discipline
around that decision.

## Why this agent proposes and never moves

`perform()` writes nothing. It reads the declared roots, classifies what it
finds, and returns a plan. The base class then suspends the agent in
`requires_approval` (ADR-006), because the failure mode here is not a bad
suggestion — it is a hundred files moved into folders nobody asked for, on an
inference that was wrong.

Applying the plan is a separate call, `apply_plan()`, which refuses without an
approved request. Every move it performs goes through `ReversibleFiles`, so the
whole plan can be undone file by file.

## What it refuses to do

- **No writing outside a declared root**, and none into a read-only one. The
  root layer enforces it; this agent does not re-implement the check.
- **No deletion.** Ever. The most an organiser does is archive.
- **No guessing when nothing is declared**: with no root, it reports how to
  declare one instead of returning an empty plan that looks like "nothing to do".
"""

import os
from typing import Any, Dict, List, Optional

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.storage.roots import VARIABLE, Root, declared_roots

#: Catégories de rangement, par extension. Un fichier dont l'extension n'est
#: dans aucune catégorie **n'est pas rangé** : le classer dans « divers »
#: donnerait un dossier fourre-tout qui reproduit le désordre d'origine.
CATEGORIES = {
    "documents": (".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md"),
    "tableurs": (".xls", ".xlsx", ".ods", ".csv"),
    "images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"),
    "audio": (".mp3", ".wav", ".ogg", ".flac", ".m4a"),
    "video": (".mp4", ".avi", ".mkv", ".mov", ".webm"),
    "archives": (".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"),
    "code": (".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".sh"),
}

#: Nombre maximal de fichiers examinés par racine. Une racine peut contenir des
#: centaines de milliers de fichiers ; un plan que personne ne peut relire n'est
#: pas approuvable, et un plan non approuvable ne sert à rien.
LIMITE_FICHIERS = 500


class FileOrganizerAgent(BaseAgent):
    """Agent qui propose un rangement de fichiers, et ne l'exécute qu'approuvé."""

    agent_id = "organizer"
    required_engines = ("tool", "memory")
    approval_required = True
    approval_description = (
        "Ranger des fichiers dans les racines déclarées. Chaque déplacement est "
        "journalisé et annulable ; rien n'est supprimé."
    )

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Construit le plan de rangement, sans rien déplacer.

        Args:
            context: Contexte d'exécution.

        Returns:
            Le plan proposé, ou l'état qui empêche d'en produire un.
        """
        racines = declared_roots()
        if not racines:
            return {
                "status": "no_roots",
                "reason": (
                    f"Aucune racine déclarée : {VARIABLE} est vide. Sans racine, "
                    "l'agent n'a accès à aucun fichier."
                ),
                "example": f"{VARIABLE}=documents:/home/awa/Documents:rw",
                "proposals": [],
            }

        inscriptibles = [racine for racine in racines if racine.writable]
        if not inscriptibles:
            return {
                "status": "read_only",
                "reason": (
                    "Toutes les racines déclarées sont en lecture seule : un "
                    "rangement y est impossible. Les déclarer « :rw » pour "
                    "l'autoriser."
                ),
                "roots": [racine.name for racine in racines],
                "proposals": [],
            }

        propositions: List[Dict[str, str]] = []
        examines = 0
        for racine in inscriptibles:
            fichiers = self._fichiers_a_ranger(racine)
            examines += len(fichiers)
            propositions.extend(self._proposer(racine, fichiers))

        return {
            "status": "planned" if propositions else "nothing_to_do",
            "roots": [racine.name for racine in inscriptibles],
            "files_examined": examines,
            "proposals": propositions,
            "categories": sorted({p["category"] for p in propositions}),
            # Dit explicitement : ce résultat n'a rien changé sur le disque.
            "applied": False,
            "note": (
                "Aucun fichier n'a été déplacé. L'application demande une "
                "approbation, et chaque déplacement reste annulable."
            ),
        }

    def _fichiers_a_ranger(self, racine: Root) -> List[str]:
        """
        Liste les fichiers **à la racine même**, jamais dans ses sous-dossiers.

        Un fichier déjà placé dans un dossier est un fichier que quelqu'un a
        rangé. Le déplacer parce que son extension suggère autre chose
        défait un choix humain, ce qu'un organisateur ne doit jamais faire.
        """
        try:
            entrees = sorted(os.listdir(racine.path))
        except OSError:
            return []

        fichiers = []
        for nom in entrees:
            if nom.startswith("."):
                # Les fichiers cachés — et la corbeille du chapitre 07 — sont
                # laissés là où ils sont.
                continue
            if os.path.isfile(os.path.join(racine.path, nom)):
                fichiers.append(nom)
            if len(fichiers) >= LIMITE_FICHIERS:
                break
        return fichiers

    def _proposer(self, racine: Root, fichiers: List[str]) -> List[Dict[str, str]]:
        """Associe à chaque fichier classable sa destination."""
        propositions = []
        for nom in fichiers:
            categorie = self._categorie_de(nom)
            if categorie is None:
                continue
            propositions.append({
                "root": racine.name,
                "source": f"{racine.name}/{nom}",
                "destination": f"{racine.name}/{categorie}/{nom}",
                "category": categorie,
                "reason": f"extension {os.path.splitext(nom)[1] or '(aucune)'}",
            })
        return propositions

    @staticmethod
    def _categorie_de(nom: str) -> Optional[str]:
        """Retourne la catégorie d'un fichier, ou None s'il n'en a pas."""
        extension = os.path.splitext(nom)[1].lower()
        for categorie, extensions in CATEGORIES.items():
            if extension in extensions:
                return categorie
        return None

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply_plan(
        self,
        context: AgentContext,
        proposals: List[Dict[str, str]],
        approval_request_id: str,
    ) -> Dict[str, Any]:
        """
        Exécute un plan **approuvé**.

        Args:
            context: Contexte d'exécution, porteur du portillon.
            proposals: Propositions rendues par `perform`.
            approval_request_id: Identifiant de la demande approuvée.

        Returns:
            Les opérations effectuées, chacune avec son identifiant d'annulation,
            et les refus rencontrés.

        Raises:
            PermissionError: La demande n'est pas approuvée. Lever est correct :
                ranger sans décision humaine est ce que ce module empêche.
        """
        if not self._est_approuve(context, approval_request_id):
            raise PermissionError(
                f"Plan non approuvé (« {approval_request_id} ») : aucun fichier "
                "n'a été déplacé."
            )

        from src.storage.reversible import ReversibleFiles

        # Le plan est **recalculé** et l'exécution s'y limite. Sans cela,
        # l'approbation porterait sur « l'agent range » et non sur ce qu'il
        # range : un appelant pourrait présenter une demande approuvée puis lui
        # faire déplacer des chemins que l'agent n'a jamais proposés.
        autorisees = {
            (proposition["source"], proposition["destination"])
            for proposition in self.perform(context).get("proposals", [])
        }

        fichiers = ReversibleFiles(declared_roots())
        effectuees: List[Dict[str, Any]] = []
        refus: List[Dict[str, str]] = []

        for proposition in proposals:
            couple = (proposition.get("source"), proposition.get("destination"))
            if couple not in autorisees:
                refus.append({
                    "source": proposition.get("source", "?"),
                    "reason": (
                        "Déplacement absent du plan que l'agent propose : "
                        "l'approbation ne couvre pas ce chemin."
                    ),
                })
                continue
            try:
                operation = fichiers.move(
                    proposition["source"], proposition["destination"],
                    raison=f"rangement automatique ({proposition.get('category', '?')})",
                )
                effectuees.append(operation.to_dict())
            except Exception as erreur:  # noqa: BLE001 - un refus est une donnée
                # Un échec sur un fichier n'arrête pas le plan : les autres
                # fichiers sont rangés, et le refus est rendu avec sa raison.
                refus.append({"source": proposition.get("source", "?"), "reason": str(erreur)})

        context.post("files_organized", {"moved": len(effectuees), "refused": len(refus)})
        return {
            "status": "applied" if effectuees else "nothing_applied",
            "moved": effectuees,
            "moved_count": len(effectuees),
            "refused": refus,
            "undo": [operation["id"] for operation in effectuees],
            "note": "Chaque déplacement est annulable par son identifiant.",
        }

    @staticmethod
    def _est_approuve(context: AgentContext, approval_request_id: str) -> bool:
        """
        Vérifie qu'une demande est réellement approuvée.

        Un portillon absent vaut **non approuvé** : sans lui, rien ne peut
        attester d'une décision humaine.
        """
        portillon = context.approval
        if portillon is None or not approval_request_id:
            return False
        try:
            demande = portillon.get(approval_request_id)
        except Exception:  # noqa: BLE001 - un portillon en panne ne vaut pas un accord
            return False
        # Le statut est une chaîne dans le moteur en mémoire et une énumération
        # ailleurs : lire l'un des deux seulement rendait « non approuvé » sur
        # une demande approuvée, donc un refus silencieux au mauvais moment.
        statut = getattr(demande, "status", None)
        return getattr(statut, "value", statut) == "approved"


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(FileOrganizerAgent, input_data)
