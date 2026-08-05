"""
Base Agent for GalSen IA.

Every agent of the platform derives from `BaseAgent`. The base class handles
what is identical for all agents — result shape, error isolation, timing and
memory tracing — so that a concrete agent only writes what makes it different:
its `perform` method.
"""

import abc
import logging
import time
from typing import Any, Dict, List, Optional

from .context import AgentContext


class AgentResult:
    """
    Résultat standard d'une exécution d'agent.

    La forme du dictionnaire produit est celle attendue par le Router Engine,
    l'Agent Runtime et le Result Aggregator : `agent`, `status`, `result`.
    """

    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_SKIPPED = "skipped"
    STATUS_REQUIRES_APPROVAL = "requires_approval"

    def __init__(
        self,
        agent: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
        engines_used: Optional[List[str]] = None,
        duration_seconds: float = 0.0,
        approval_request_id: Optional[str] = None,
    ):
        """
        Initialise le résultat.

        Args:
            agent: Identifiant de l'agent
            status: `success`, `error`, `skipped` ou `requires_approval`
            result: Charge utile produite par l'agent
            error: Message d'erreur si le statut est `error`
            engines_used: Moteurs réellement sollicités pendant l'exécution
            duration_seconds: Durée de l'exécution
            approval_request_id: Identifiant de la demande d'approbation
                si le statut est `requires_approval`
        """
        self.agent = agent
        self.status = status
        self.result = result
        self.error = error
        self.engines_used = engines_used or []
        self.duration_seconds = duration_seconds
        self.approval_request_id = approval_request_id

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat au format attendu par les orchestrateurs."""
        payload: Dict[str, Any] = {
            "agent": self.agent,
            "status": self.status,
            "result": self.result,
            "engines_used": self.engines_used,
            "duration_seconds": round(self.duration_seconds, 3),
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.approval_request_id is not None:
            payload["approval_request_id"] = self.approval_request_id
        return payload


class BaseAgent(abc.ABC):
    """
    Classe de base de tous les agents GalSen IA.

    Un agent concret déclare son identifiant, les moteurs dont il a besoin, et
    implémente `perform`. Il ne gère ni les exceptions, ni le format de sortie,
    ni la trace en mémoire : la classe de base s'en charge.
    """

    # Identifiant de l'agent dans `agents/registry.yaml`
    agent_id: str = "base"

    # Moteurs que l'agent utilise. Sert au diagnostic et à la documentation :
    # un moteur absent n'empêche pas l'agent de s'exécuter.
    required_engines: tuple = ()

    # Portillon d'approbation humaine (ADR-006). Par défaut aucun agent n'est
    # concerné : une sous-classe passe `approval_required = True` pour que son
    # action soit suspendue dans l'état `requires_approval` jusqu'à une
    # décision humaine.
    approval_required: bool = False

    # Description et niveau de confiance facultatifs portés par la demande
    # d'approbation, pour que l'opérateur humain puisse décider en connaissance
    # de cause.
    approval_description: Optional[str] = None
    approval_confidence: Optional[float] = None

    def __init__(self):
        """Initialise l'agent."""
        self.logger = logging.getLogger(f"{__name__}.{self.agent_id}")

    @abc.abstractmethod
    def perform(self, context: AgentContext) -> Any:
        """
        Exécute le travail propre à l'agent.

        Args:
            context: Contexte d'exécution donnant accès aux moteurs

        Returns:
            La charge utile du résultat, librement structurée par l'agent
        """

    def run(self, context: AgentContext) -> Dict[str, Any]:
        """
        Exécute l'agent et retourne un résultat au format standard.

        Une exception levée par `perform` est convertie en résultat d'erreur :
        l'échec d'un agent ne doit jamais interrompre la plateforme.

        Args:
            context: Contexte d'exécution

        Returns:
            Résultat de l'agent au format attendu par les orchestrateurs
        """
        started_at = time.time()

        try:
            payload = self.perform(context)
            duration = time.time() - started_at

            if self.approval_required:
                result_dict = self._run_gated(context, payload, duration)
            else:
                result = AgentResult(
                    agent=self.agent_id,
                    status=AgentResult.STATUS_SUCCESS,
                    result=payload,
                    engines_used=list(self.required_engines),
                    duration_seconds=duration,
                )
                self._trace(context, result)
                result_dict = result.to_dict()
                self._record_audit(context, result_dict)
            return result_dict

        except Exception as error:
            duration = time.time() - started_at
            self.logger.error(f"Agent '{self.agent_id}' en échec: {error}", exc_info=True)
            result_dict = AgentResult(
                agent=self.agent_id,
                status=AgentResult.STATUS_ERROR,
                error=str(error),
                engines_used=list(self.required_engines),
                duration_seconds=duration,
            ).to_dict()
            self._record_audit(context, result_dict)
            return result_dict

    def _run_gated(
        self, context: AgentContext, payload: Any, duration: float
    ) -> Dict[str, Any]:
        """
        Soumet l'action de l'agent au portillon d'approbation humaine.

        L'action est suspendue dans l'état `requires_approval` en attendant une
        décision. Si le portillon est indisponible, le résultat est une erreur :
        une action qui ne peut pas être validée ne doit jamais être considérée
        comme exécutée.
        """
        approval_request_id = context.submit_approval(
            action=f"agent:{self.agent_id}",
            description=self.approval_description,
            confidence=self.approval_confidence,
        )

        if approval_request_id is None:
            self.logger.error(
                f"Agent '{self.agent_id}' : le portillon d'approbation est indisponible"
            )
            result_dict = AgentResult(
                agent=self.agent_id,
                status=AgentResult.STATUS_ERROR,
                error="Le portillon d'approbation est indisponible : action non validée.",
                engines_used=list(self.required_engines),
                duration_seconds=duration,
            ).to_dict()
            self._record_audit(context, result_dict)
            return result_dict

        result = AgentResult(
            agent=self.agent_id,
            status=AgentResult.STATUS_REQUIRES_APPROVAL,
            result=payload,
            engines_used=list(self.required_engines),
            duration_seconds=duration,
            approval_request_id=approval_request_id,
        )
        self._trace(context, result)
        result_dict = result.to_dict()
        self._record_audit(context, result_dict)
        return result_dict

    def _record_audit(self, context: AgentContext, result: Dict[str, Any]) -> None:
        """
        Consigne l'exécution de l'agent dans le système d'audit.

        L'audit est facultatif : son échec ou son absence ne doit pas modifier
        le résultat retourné à l'appelant.
        """
        try:
            context.record_audit(
                "agent",
                f"agent:{self.agent_id}",
                status=result.get("status", "error"),
                execution_time_seconds=result.get("duration_seconds", 0.0),
                detail=result.get("error"),
                metadata={"engines_used": result.get("engines_used", [])},
            )
        except Exception as error:
            self.logger.warning(f"Consignation de l'audit de l'agent '{self.agent_id}' impossible: {error}")

    def _trace(self, context: AgentContext, result: AgentResult) -> None:
        """
        Consigne le passage de l'agent en mémoire partagée.

        Les agents suivants peuvent ainsi retrouver ce qui a déjà été fait dans
        la requête. L'échec de cette trace ne compromet pas le résultat.
        """
        context.remember(
            content={"agent": self.agent_id, "result": result.result},
            memory_type="agent_shared",
            tags=[self.agent_id, "agent_result"],
        )
