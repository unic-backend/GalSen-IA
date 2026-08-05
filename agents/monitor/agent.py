"""
Monitoring Agent for GalSen IA.

Reports the live state of the platform: which engines answer, what the log file
contains, and how the current request went.

This is the agent that makes an integration failure visible. If an engine stops
being reachable, it appears here rather than surfacing later as an unexplained
empty result somewhere else.
"""

import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class MonitorAgent(BaseAgent):
    """Agent qui rend compte de l'état de santé de la plateforme."""

    agent_id = "monitor"
    required_engines = ("memory", "knowledge", "document", "vision", "model", "tool")

    # Journal inspecté par défaut
    LOG_PATH = "logs/application.log"

    # Nombre de lignes de journal analysées, en partant de la fin
    LOG_TAIL_LINES = 500

    _LOG_LEVEL_PATTERN = re.compile(r'\b(CRITICAL|ERROR|WARNING|INFO|DEBUG)\b')

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Collecte l'état de la plateforme.

        Args:
            context: Contexte d'exécution

        Returns:
            Disponibilité des moteurs, analyse du journal, statistiques et alertes
        """
        engines = context.registry.availability()
        logs = self._analyze_logs(context)
        engine_stats = self._collect_engine_stats(context)
        pipeline = self._summarize_pipeline(context)

        alerts = self._build_alerts(engines, logs, pipeline, engine_stats)

        return {
            "engines": engines,
            "engines_available": sum(1 for state in engines.values() if state["available"]),
            "engines_total": len(engines),
            "logs": logs,
            "engine_stats": engine_stats,
            "pipeline": pipeline,
            "alerts": alerts,
            "health": self._health(engines, alerts),
        }

    def _analyze_logs(self, context: AgentContext) -> Dict[str, Any]:
        """
        Compte les niveaux de journalisation dans les dernières lignes du journal.

        La lecture se fait par la fin : un journal de production dépasse vite
        toute limite de lecture intégrale, et seules les lignes récentes
        renseignent sur l'état courant.
        """
        outcome = context.use_tool(
            "filesystem", "tail", self.LOG_PATH, lines=self.LOG_TAIL_LINES
        )
        if outcome.get("status") != "success":
            return {"available": False, "reason": outcome.get("error", "Journal illisible")}

        lines = outcome["result"]["lines"]

        counts: Dict[str, int] = {}
        recent_errors: List[str] = []

        for line in lines:
            match = self._LOG_LEVEL_PATTERN.search(line)
            if not match:
                continue

            level = match.group(1)
            counts[level] = counts.get(level, 0) + 1

            if level in ("ERROR", "CRITICAL") and len(recent_errors) < 10:
                recent_errors.append(line.strip()[:200])

        return {
            "available": True,
            "path": self.LOG_PATH,
            "file_size": outcome["result"]["file_size"],
            "lines_analyzed": len(lines),
            "level_counts": counts,
            "error_count": counts.get("ERROR", 0) + counts.get("CRITICAL", 0),
            "warning_count": counts.get("WARNING", 0),
            "recent_errors": recent_errors,
        }

    def _collect_engine_stats(self, context: AgentContext) -> Dict[str, Any]:
        """
        Interroge les moteurs qui savent rendre compte de leur contenu.

        Un moteur indisponible ou sans statistiques est simplement absent du
        résultat : ce n'est pas une erreur de supervision.
        """
        stats: Dict[str, Any] = {}

        document_engine = context.registry.try_get("document")
        if document_engine is not None and hasattr(document_engine, "get_stats"):
            stats["document"] = document_engine.get_stats()

        knowledge_engine = context.registry.try_get("knowledge")
        if knowledge_engine is not None and hasattr(knowledge_engine, "get_stats"):
            stats["knowledge"] = knowledge_engine.get_stats()

        model_engine = context.registry.try_get("model")
        if model_engine is not None:
            model_stats: Dict[str, Any] = {
                "registered_models": len(model_engine.list_models()),
            }
            # L'état des fournisseurs explique pourquoi la génération de texte
            # fonctionne ou non : c'est l'information la plus utile du moteur
            if hasattr(model_engine, "get_provider_status"):
                providers = model_engine.get_provider_status()
                model_stats.update({
                    "providers": providers,
                    "providers_available": sum(
                        1 for state in providers.values() if state["status"] == "ready"
                    ),
                    "providers_total": len(providers),
                    "catalogue_size": len(model_engine.list_catalogue()),
                    "generation_available": model_engine.has_available_provider(),
                })
            stats["model"] = model_stats

        tool_engine = context.registry.try_get("tool")
        if tool_engine is not None:
            stats["tool"] = {
                "enabled_tools": len(tool_engine.list_enabled_tools()),
                "categories": tool_engine.get_tool_categories(),
            }

        return stats

    def _summarize_pipeline(self, context: AgentContext) -> Dict[str, Any]:
        """Résume le déroulement des agents déjà exécutés dans la requête."""
        results = context.previous_results

        failed = [
            result.get("agent") for result in results
            if result.get("status") != "success"
        ]

        return {
            "agents_executed": len(results),
            "agents_failed": failed,
            "total_duration_seconds": round(
                sum(result.get("duration_seconds", 0) or 0 for result in results), 3
            ),
        }

    def _build_alerts(
        self,
        engines: Dict[str, Dict[str, Any]],
        logs: Dict[str, Any],
        pipeline: Dict[str, Any],
        engine_stats: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Transforme les anomalies constatées en alertes exploitables."""
        alerts: List[Dict[str, str]] = []

        for name, state in engines.items():
            if not state["available"]:
                alerts.append({
                    "severity": "critical",
                    "source": f"engine:{name}",
                    "message": f"Moteur '{name}' indisponible: {state['reason']}",
                })

        if logs.get("available") and logs.get("error_count", 0) > 0:
            alerts.append({
                "severity": "high",
                "source": "logs",
                "message": f"{logs['error_count']} erreur(s) dans les {logs['lines_analyzed']} dernières lignes",
            })

        model_stats = engine_stats.get("model")
        if model_stats is not None and not model_stats.get("generation_available", True):
            alerts.append({
                "severity": "warning",
                "source": "engine:model",
                "message": (
                    f"Aucun fournisseur de modèles disponible "
                    f"({model_stats.get('providers_total', 0)} enregistrés): "
                    "la génération de texte est impossible"
                ),
            })

        for agent_id in pipeline.get("agents_failed", []):
            alerts.append({
                "severity": "high",
                "source": f"agent:{agent_id}",
                "message": f"L'agent '{agent_id}' a échoué pendant cette requête",
            })

        return alerts

    def _health(self, engines: Dict[str, Dict[str, Any]], alerts: List[Dict[str, str]]) -> Dict[str, Any]:
        """Établit l'état de santé global."""
        unavailable = [name for name, state in engines.items() if not state["available"]]
        critical_alerts = [alert for alert in alerts if alert["severity"] == "critical"]

        if critical_alerts:
            status = "degraded"
        elif alerts:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "unavailable_engines": unavailable,
            "alert_count": len(alerts),
        }


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(MonitorAgent, input_data)
