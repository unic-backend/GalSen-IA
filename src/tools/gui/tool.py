"""
Contrôle d'interface graphique, sous portillon (VOLET 34, ch. 06).

Le chapitre 05 a donné des yeux ; celui-ci donne une main. Les deux sont séparés
à dessein : un agent peut recevoir la vue sans recevoir le geste.

## La règle qui tient tout le reste

**Une action nomme sa cible, ou elle est refusée** (ADR-017 §4). Un `GUIAction`
vise un `ScreenElement` — rôle, libellé, bornes — jamais un couple de
coordonnées. Ce n'est pas de la prudence : une demande d'approbation qui dit
« cliquer en (412, 380) » ne peut pas être évaluée par l'humain qui la reçoit, et
une approbation qu'on ne peut pas évaluer est un tampon assorti d'une trace.

## Le chemin, identique à celui de l'écriture de code (VOLET 31)

    propose(action) → demande d'approbation, **rien ne bouge**
    un humain décide
    apply(identifiant) → le geste, seulement si la décision est « approuvée »

`GuardedEditor` a établi ce chemin pour les fichiers ; le reprendre à l'identique
évite d'avoir deux portillons qui finiraient par diverger.

## Ce qui est refusé avant même d'atteindre le portillon

| Refus | Pourquoi |
|---|---|
| Cible absente | Rien à nommer, donc rien à approuver |
| Cible sans bornes | On ne peut pas agir sur ce qu'on ne sait pas situer |
| Élément désactivé | Le geste ne ferait rien, et serait rapporté comme fait |
| Champ de mot de passe | Une saisie de secret par un agent est un chemin d'identifiants ; il se décide ailleurs qu'ici |
| Aucun moteur d'approbation | Un portillon qu'on peut faire disparaître n'est pas un portillon |
"""

import logging
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool
from src.tools.screen.types import ScreenElement

from .backends import executants
from .interfaces import ApprovalRequired, GUIBackend, GUIUnavailable
from .types import ActionKind, ActionOutcome, GUIAction

logger = logging.getLogger(__name__)

# Rôles d'accessibilité qui désignent un champ de secret. Une saisie d'agent y
# est refusée : le portillon protège l'action, pas la valeur, et une valeur
# secrète traversant un agent est un problème d'identifiants, pas d'approbation.
ROLES_DE_SECRET = ("password", "password text", "secure text field", "mot de passe")

# Le statut qu'une demande doit porter pour qu'un geste s'exécute.
STATUT_ACCORDE = "approved"


class GUITool(BaseTool):
    """Propose des gestes, et n'en exécute aucun sans décision humaine."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        context: Any = None,
        backends: Optional[List[GUIBackend]] = None,
    ) -> None:
        """
        Args:
            config: Configuration de l'outil.
            context: `AgentContext` de l'agent — il porte le portillon, l'audit
                et l'identité. **Sans lui, l'outil ne peut rien proposer.**
            backends: Exécutants à utiliser ; ceux de la plateforme sinon.
        """
        super().__init__(config)
        self._context = context
        self._backends = backends
        # Actions proposées, en attente : identifiant de demande → action.
        self._en_attente: Dict[str, GUIAction] = {}

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération.

        Args:
            *args: L'opération — `availability`, `propose`, `apply` — puis ses
                arguments.
            **kwargs: Options de l'opération.
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
        Décrit ce qui peut agir, et ce qui manque au reste.

        Répond toujours, y compris sans écran et sans portillon : c'est ainsi
        qu'un agent constate qu'il n'a pas de main, au lieu de le déduire d'un
        échec.
        """
        candidats = executants(self._backends)
        rapport = [
            {
                "backend": backend.name,
                "available": backend.available(),
                "reason": backend.unavailable_reason(),
            }
            for backend in candidats
        ]
        utilisables = [ligne for ligne in rapport if ligne["available"]]
        return {
            "can_act": bool(utilisables) and self._portillon_present(),
            "approval_gate": self._portillon_present(),
            "preferred": utilisables[0]["backend"] if utilisables else None,
            "backends": rapport,
        }

    def _op_propose(self, action: GUIAction) -> Dict[str, Any]:
        """
        Soumet un geste au portillon, **sans rien exécuter**.

        Args:
            action: Le geste voulu, avec sa cible et sa raison.

        Returns:
            `pending_approval` avec l'identifiant de la demande, ou `refused`
            avec ce qui a motivé le refus.
        """
        return self._proposer(action).to_dict()

    def _op_apply(self, approval_request_id: str) -> Dict[str, Any]:
        """
        Exécute un geste **approuvé**.

        Args:
            approval_request_id: Identifiant rendu par `propose`.

        Raises:
            ApprovalRequired: La demande est inconnue, en attente ou refusée.
        """
        return self._appliquer(approval_request_id).to_dict()

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _portillon_present(self) -> bool:
        """Indique si un moteur d'approbation est joignable."""
        return self._context is not None and getattr(self._context, "approval", None) is not None

    def _refus_de_forme(self, action: GUIAction) -> Optional[str]:
        """
        Retourne ce qui disqualifie une action, avant tout portillon.

        Ces refus précèdent l'approbation à dessein : ils portent sur des gestes
        qu'un humain ne devrait pas avoir à évaluer, parce qu'ils sont
        inexécutables, illisibles, ou hors du domaine du portillon.
        """
        if not action.reason or not action.reason.strip():
            return (
                "Une raison est exigée : un humain doit pouvoir décider sans "
                "reconstituer l'intention de l'agent."
            )

        if action.kind is ActionKind.PRESS and action.target is None:
            return None  # Une touche sur le focus courant est le seul cas sans cible.

        cible = action.target
        if cible is None:
            return (
                "Aucune cible : une action doit pouvoir se nommer pour être "
                "approuvée (ADR-017 §4)."
            )
        if not cible.label and not cible.identifier:
            return (
                f"Cible sans libellé ni identifiant ({cible.role}) : la demande "
                "d'approbation serait illisible."
            )
        if cible.bounds is None:
            return f"Cible sans position connue : {cible.describe()}."
        if not cible.enabled:
            return (
                f"Élément désactivé : {cible.describe()}. Le geste ne ferait "
                "rien et serait rapporté comme fait."
            )
        if action.kind is ActionKind.TYPE:
            if cible.role.lower() in ROLES_DE_SECRET:
                return (
                    f"Saisie refusée dans un champ de secret ({cible.role}) : un "
                    "identifiant qui passe par un agent est un problème "
                    "d'identifiants, que le portillon ne résout pas."
                )
            if not action.text:
                return "Saisie vide : rien à faire."
        return None

    def _proposer(self, action: GUIAction) -> ActionOutcome:
        """Applique les refus de forme, puis soumet au portillon."""
        refus = self._refus_de_forme(action)
        if refus is not None:
            return ActionOutcome(status="refused", detail=refus, action=action)

        if not self._portillon_present():
            # Ailleurs, un moteur absent dégrade proprement. Ici il ferme, comme
            # pour l'écriture de code (VOLET 31).
            return ActionOutcome(
                status="refused", action=action,
                detail="Moteur d'approbation indisponible : aucun geste n'est "
                       "possible (ADR-006).",
            )

        demande = self._context.submit_approval(
            action=f"gui:{action.kind.value}",
            description=f"{action.reason} — {action.describe()}",
            metadata=action.to_dict(),
        )
        if demande is None:
            return ActionOutcome(
                status="refused", action=action,
                detail="Le portillon a refusé la soumission : rien n'est exécuté.",
            )

        self._en_attente[demande] = action
        return ActionOutcome(
            status="pending_approval", approval_request_id=demande, action=action,
            detail="En attente d'une décision humaine. Rien n'est exécuté tant "
                   "qu'elle n'est pas prise.",
        )

    def _appliquer(self, approval_request_id: str) -> ActionOutcome:
        """Exécute un geste dont la demande porte le statut « approuvé »."""
        action = self._en_attente.get(approval_request_id)
        if action is None:
            raise ApprovalRequired(
                f"Demande « {approval_request_id} » inconnue de cet outil : "
                "aucun geste ne s'exécute sur un identifiant qu'on n'a pas proposé."
            )

        demande = self._context.approval.get(approval_request_id)
        statut = getattr(demande, "status", None) if demande else None
        if statut != STATUT_ACCORDE:
            raise ApprovalRequired(
                f"Geste refusé : la demande « {approval_request_id} » porte le "
                f"statut « {statut} », pas « {STATUT_ACCORDE} »."
            )

        utilisables = [backend for backend in executants(self._backends) if backend.available()]
        if not utilisables:
            raisons = "; ".join(
                f"{backend.name} : {backend.unavailable_reason()}"
                for backend in executants(self._backends)
            )
            raise GUIUnavailable(f"Aucun exécutant disponible. {raisons}")

        backend = utilisables[0]
        if action.kind in (ActionKind.CLICK, ActionKind.DOUBLE_CLICK):
            backend.click(action.target, double=action.kind is ActionKind.DOUBLE_CLICK)
        elif action.kind is ActionKind.TYPE:
            backend.type_text(action.target, action.text)
        else:
            backend.press(action.key, action.target)

        # Le geste n'est plus en attente : rejouer une approbation permettrait de
        # cliquer deux fois avec une seule décision.
        del self._en_attente[approval_request_id]

        self._tracer(action, backend.name)
        return ActionOutcome(
            status="done", approval_request_id=approval_request_id, action=action,
            detail=f"Exécuté par « {backend.name} ».",
        )

    def _tracer(self, action: GUIAction, backend: str) -> None:
        """Inscrit le geste au journal d'audit, sans le texte saisi."""
        enregistrer = getattr(self._context, "record_audit", None)
        if enregistrer is None:
            return
        try:
            from src.audit_engine.types import AuditEventType

            enregistrer(
                AuditEventType.TOOL,
                f"gui:{action.kind.value}",
                detail=action.describe(),
                metadata={**action.to_dict(), "backend": backend},
            )
        except Exception as erreur:  # noqa: BLE001 - une trace ratée ne défait pas le geste
            logger.warning("Geste exécuté mais non tracé : %s", erreur)


__all__ = [
    "ROLES_DE_SECRET",
    "ActionKind",
    "ActionOutcome",
    "ApprovalRequired",
    "GUIAction",
    "GUITool",
    "GUIUnavailable",
    "ScreenElement",
]
