"""
Agent Runtime for GalSen IA.

The Agent Runtime receives tasks from the Router Engine, executes agents,
manages dependencies, handles failures, and returns unified responses.
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Set
from ..router.config_loader import ConfigLoader
from ..router.agent_loader import AgentLoader
from ..router.workflow_loader import WorkflowLoader
from ..router.result_aggregator import ResultAggregator
from ..router.retry_manager import RetryManager
from ..router.logger import Logger
from ..integration.engine_registry import get_shared_registry
from ..audit_engine.types import AuditEventType, AuditStatus, generate_request_id
from .context import AgentContext


class AgentRuntime:
    """Execution engine for running agents according to workflow definitions."""

    def __init__(self):
        """Initialize the Agent Runtime with configuration loaders."""
        # Determine project root (two levels up from this file)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # Initialize configuration loaders (reusing router's loaders)
        self.config_loader = ConfigLoader(
            os.path.join(project_root, 'config', 'settings.yaml')
        )
        self.agent_loader = AgentLoader(
            os.path.join(project_root, 'agents', 'registry.yaml')
        )
        self.workflow_loader = WorkflowLoader(
            os.path.join(project_root, 'workflows', 'workflows.yaml')
        )
        self.result_aggregator = ResultAggregator()
        self.retry_manager = RetryManager(
            max_attempts=self.config_loader.get(
                'workflows.execution.failure.max_attempts', 3
            ),
            delay_seconds=1.0
        )
        self.logger_manager = Logger(self.config_loader)
        self.logger = self.logger_manager.get_logger(__name__)

        # Le dispatcher est créé une fois : il met en cache les classes d'agents
        from ..router.agent_dispatcher import AgentDispatcher
        self.agent_dispatcher = AgentDispatcher()

        # Registre partagé avec le reste de la plateforme
        self.engine_registry = get_shared_registry()

        # Les agents parallèles écrivent leurs résultats dans le contexte commun
        self._results_lock = threading.Lock()

        self.logger.info("AgentRuntime initialized successfully.")

    def execute_task(
        self,
        task_input: Any,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a task using the specified workflow.

        Args:
            task_input: Input data for the task (typically a user request string).
            workflow_id: Identifier of workflow to use (defaults to default workflow).
            user_id: User the task belongs to, used to isolate memories.
            session_id: Session the task belongs to.

        Returns:
            Dictionary containing execution results and metadata.
        """
        start_time = time.time()
        request_id = generate_request_id()
        # Le contexte n'est créé qu'après les premières étapes de configuration ;
        # il doit rester None tant que le chargement du workflow n'a pas réussi.
        context: Optional[AgentContext] = None
        # Résolu pendant le try ; None si le chargement du workflow échoue.
        workflow_id_to_use: Optional[str] = None
        self.logger.info(
            f"Starting task execution: {str(task_input)[:100]}..."
        )

        try:
            # Determine workflow to use
            workflow_id_to_use = (
                workflow_id or self.workflow_loader.get_default_workflow()
            )
            workflow = self.workflow_loader.get_workflow(workflow_id_to_use)
            self.logger.info(
                f"Using workflow: '{workflow_id_to_use}'"
            )

            # Get pipeline (excluding router, which is the orchestrator)
            pipeline = workflow.get('pipeline', [])
            # Filter out the router agent since it's the orchestrator itself
            agent_pipeline = [
                agent_id for agent_id in pipeline if agent_id != 'router'
            ]

            # Get parallel agent set from workflow execution config
            execution_config = workflow.get('execution', {})
            parallel_agents_set: Set[str] = set(
                execution_config.get('parallel_agents', [])
            )

            # One context is shared by every agent of the task, so they all see
            # the same memory, the same session and each other's results
            context = AgentContext(
                request=task_input,
                agent_id='runtime',
                registry=self.engine_registry,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )

            # Execute agents with mixed sequential/parallel handling
            agent_results = self._execute_agent_pipeline(
                agent_pipeline, parallel_agents_set, task_input, context
            )

            # Aggregate results from all executed agents
            aggregated_result = self.result_aggregator.aggregate(
                agent_results
            )

            # Prepare final response
            end_time = time.time()
            execution_time = end_time - start_time

            successful_agents = sum(
                1 for r in agent_results if r.get('status') == 'success'
            )
            pending_approval_agents = sum(
                1 for r in agent_results if r.get('status') == 'requires_approval'
            )
            failed_agents = (
                len(agent_results) - successful_agents - pending_approval_agents
            )

            if failed_agents > 0:
                status = "partial_success"
            elif pending_approval_agents > 0:
                # Aucune erreur mais au moins une action attend une décision
                # humaine : la requête est suspendue (ADR-006).
                status = "requires_approval"
            else:
                status = "success"

            approval_request_ids = [
                r.get('approval_request_id')
                for r in agent_results
                if r.get('status') == 'requires_approval'
                and r.get('approval_request_id')
            ]

            response = {
                "status": status,
                "task_input": task_input,
                "workflow_used": workflow_id_to_use,
                "execution_time_seconds": round(execution_time, 2),
                "agent_results": agent_results,
                "aggregated_result": aggregated_result,
                "metadata": {
                    "total_agents_executed": len(agent_results),
                    "successful_agents": successful_agents,
                    "failed_agents": failed_agents,
                    "pending_approval_agents": pending_approval_agents,
                }
            }
            if approval_request_ids:
                response["approval_request_ids"] = approval_request_ids

            self.logger.info(
                f"Task completed in {execution_time:.2f}s. "
                f"Status: {response['status']}, "
                f"Successful: {successful_agents}/{len(agent_results)}, "
                f"Pending approval: {pending_approval_agents}"
            )

            # L'audit de la requête est consigné en dernier : il résume la requête
            # et la liste des agents exécutés en une seule entrée consultable.
            if context is not None:
                context.record_audit(
                    AuditEventType.REQUEST,
                    "execute_task",
                    status=response["status"],
                    execution_time_seconds=execution_time,
                    metadata={
                        "workflow_id": workflow_id_to_use,
                        "total_agents_executed": len(agent_results),
                        "successful_agents": successful_agents,
                        "failed_agents": failed_agents,
                        "pending_approval_agents": pending_approval_agents,
                    },
                )
            response["request_id"] = request_id
            return response

        except Exception as e:
            self.logger.error(
                f"Unexpected error during task execution: {e}",
                exc_info=True
            )
            error_response = {
                "status": "error",
                "task_input": task_input,
                "error": str(e),
                "request_id": request_id,
                "execution_time_seconds": round(time.time() - start_time, 2)
            }
            if context is not None:
                context.record_audit(
                    AuditEventType.REQUEST,
                    "execute_task",
                    status=AuditStatus.FAILURE,
                    execution_time_seconds=round(time.time() - start_time, 2),
                    detail=str(e),
                    metadata={"workflow_id": workflow_id_to_use},
                )
            return error_response

    def _execute_agent_pipeline(
        self,
        pipeline: List[str],
        parallel_agents: Set[str],
        input_data: Any,
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """
        Execute agents in pipeline order with parallel execution for designated agents.

        Args:
            pipeline: Ordered list of agent IDs to execute.
            parallel_agents: Set of agent IDs that can run in parallel.
            input_data: Input data to pass to each agent.
            context: Shared execution context giving agents access to the engines.

        Returns:
            List of result dictionaries from all executed agents.
        """
        results: List[Dict[str, Any]] = []
        futures: List = []  # Stores (future, agent_id) tuples

        with ThreadPoolExecutor(
            max_workers=len(parallel_agents) or 1
        ) as executor:
            for agent_id in pipeline:
                # Skip if agent is disabled
                if not self.agent_loader.is_enabled(agent_id):
                    self.logger.warning(
                        f"Agent '{agent_id}' is disabled. Skipping."
                    )
                    continue

                agent_config = self.agent_loader.get_agent(agent_id)
                self.logger.info(
                    f"Preparing to execute agent: {agent_id}"
                )

                if agent_id in parallel_agents:
                    # Submit agent for asynchronous execution
                    future = executor.submit(
                        self._execute_agent_with_retry,
                        agent_config,
                        input_data,
                        context
                    )
                    futures.append((future, agent_id))
                    self.logger.debug(
                        f"Submitted agent '{agent_id}' for parallel execution"
                    )
                else:
                    # Wait for any pending parallel agents to complete
                    if futures:
                        self._wait_for_futures(futures, results, context)
                    # Execute agent synchronously
                    result = self._execute_agent_with_retry(
                        agent_config, input_data, context
                    )
                    results.append(result)
                    self._record_result(context, result)
                    self.logger.debug(
                        f"Completed synchronous agent: {agent_id}"
                    )

            # Wait for any remaining parallel agents to complete
            if futures:
                self._wait_for_futures(futures, results, context)

        return results

    def _wait_for_futures(
        self,
        futures: List,
        results: List[Dict[str, Any]],
        context: AgentContext
    ) -> None:
        """
        Wait for all pending futures to complete and collect their results.

        Args:
            futures: List of (future, agent_id) tuples.
            results: List to append completed results to.
            context: Shared context receiving the collected results.
        """
        for future, agent_id in futures:
            try:
                result = future.result(timeout=30)
                results.append(result)
                self._record_result(context, result)
                self.logger.debug(
                    f"Collected result from parallel agent: {agent_id}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error in parallel agent '{agent_id}': {e}"
                )
                error_result = {
                    "agent": agent_id,
                    "status": "error",
                    "error": str(e),
                    "result": None
                }
                results.append(error_result)
                self._record_result(context, error_result)
        futures.clear()

    def _record_result(
        self, context: AgentContext, result: Dict[str, Any]
    ) -> None:
        """
        Add a completed result to the shared context.

        Parallel agents finish on different threads, so the shared list is
        guarded: without the lock, two concurrent appends could be lost.

        Args:
            context: Shared execution context.
            result: Result produced by an agent.
        """
        with self._results_lock:
            context.previous_results.append(result)

    def _execute_agent_with_retry(
        self,
        agent_config: Dict[str, Any],
        input_data: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Execute a single agent with retry logic using the agent dispatcher.

        Args:
            agent_config: Configuration dictionary for the agent.
            input_data: Input data to pass to the agent.
            context: Shared execution context giving access to the engines.

        Returns:
            Result dictionary from the agent's execution.
        """
        return self.retry_manager.execute_with_retry(
            self.agent_dispatcher.dispatch,
            agent_config,
            input_data,
            context
        )