"""
Agent Runtime for GalSen IA — adaptateur historique vers `RouterEngine`.

Il y avait **deux orchestrateurs**. `RouterEngine` est exposé par
`POST /workflow/run` ; `AgentRuntime` n'avait aucune route, mais restait
importable, exporté par `src/agent/__init__.py`, et utilisé par les tests
d'intégration. Les deux chargeaient la même configuration, le même registre
d'agents, le même répartiteur et le même registre de moteurs partagé.

**Ils ne faisaient pourtant pas la même chose, et l'écart était coûteux.**
Mesuré avant ce changement, sur la même requête :

    AgentRuntime  → 9 agents exécutés (tout le pipeline du workflow)
    RouterEngine  → 2 agents exécutés (ceux que le planificateur a retenus)

`AgentRuntime` portait le chemin d'avant le planificateur : il exécutait le
pipeline entier quelle que soit la demande. Il ignorait aussi la validation des
workflows au démarrage, la trace de décision et l'historique d'exécution, que
`RouterEngine` a acquis depuis. Autrement dit, ce n'était pas un doublon inerte
mais **une seconde vérité, plus lente et moins surveillée**, qu'un appelant
pouvait prendre sans le savoir.

Il n'est pas supprimé : il est exporté, documenté et appelé. Il **délègue**
désormais, et ses appelants gagnent le pipeline piloté par le planificateur sans
changer une ligne. Le contrat de retour est préservé — la clé `task_input`
reste, là où `RouterEngine` nomme la même valeur `user_request`.

Le nouveau code appelle `RouterEngine.process_request` directement.
"""

import logging
from typing import Any, Dict, Optional

from ..router.router_engine import RouterEngine

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    Point d'entrée historique de l'exécution d'agents.

    Conservé pour les appelants existants ; toute l'exécution est faite par
    `RouterEngine`, qui est le seul orchestrateur.
    """

    def __init__(self):
        """Construit l'orchestrateur unique derrière cet adaptateur."""
        self._router = RouterEngine()
        logger.debug(
            "AgentRuntime initialisé — l'exécution est déléguée à RouterEngine."
        )

    @property
    def engine_registry(self):
        """Registre de moteurs partagé, tel que l'orchestrateur l'utilise."""
        return self._router.engine_registry

    @property
    def workflow_loader(self):
        """Chargeur de workflows, exposé par l'ancien contrat."""
        return self._router.workflow_loader

    @property
    def agent_loader(self):
        """Chargeur d'agents, exposé par l'ancien contrat."""
        return self._router.agent_loader

    def execute_task(
        self,
        task_input: Any,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exécute une tâche selon le workflow demandé.

        Args:
            task_input: Donnée d'entrée, typiquement la requête de l'utilisateur.
            workflow_id: Workflow à utiliser ; le workflow par défaut sinon.
            user_id: Utilisateur auquel rattacher la tâche, pour isoler ses mémoires.
            session_id: Session à laquelle rattacher la tâche.

        Returns:
            Le résultat de l'exécution, au format historique : la clé
            `task_input` porte la demande, comme avant la fusion.
        """
        resultat = self._router.process_request(
            task_input,
            workflow_id=workflow_id,
            user_id=user_id,
            session_id=session_id,
        )

        # Traduction du seul champ qui diffère. Renommer chez l'appelant aurait
        # été une rupture pour un gain nul.
        if "user_request" in resultat:
            resultat = dict(resultat)
            resultat["task_input"] = resultat.pop("user_request")
        return resultat
