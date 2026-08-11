"""
Planning Agent for GalSen IA.

Turns a request into an ordered task list. The decomposition is deterministic:
it comes from the intents detected in the request and from what the platform
already knows about it (memory and knowledge base), not from a language model.
The agent therefore produces the same plan for the same request, which is what
makes a plan reviewable.
"""

import re
import unicodedata
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


def _sans_accents(texte: str) -> str:
    """Retire les diacritiques, sans changer le reste du texte."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


class PlannerAgent(BaseAgent):
    """Agent qui découpe une demande en tâches ordonnées."""

    agent_id = "planner"
    required_engines = ("memory", "knowledge", "model")

    # Intentions reconnues dans une demande, et agents qu'elles mobilisent.
    # L'ordre des clés fixe l'ordre des phases du plan.
    INTENT_RULES = {
        "research": {
            "keywords": ("recherche", "rechercher", "étudier", "analyser le marché", "veille",
                         "research", "investigate", "explore", "étude", "comparer"),
            "agents": ("researcher",),
            "description": "Rassembler et vérifier l'information nécessaire",
        },
        "implementation": {
            "keywords": ("développer", "créer", "implémenter", "coder", "construire", "ajouter",
                         "build", "implement", "develop", "create", "application", "fonctionnalité"),
            "agents": ("coder",),
            "description": "Concevoir et écrire la solution",
        },
        "quality": {
            "keywords": ("tester", "qualité", "vérifier", "valider", "test", "review", "relire",
                         "corriger", "bug", "erreur"),
            "agents": ("reviewer", "tester"),
            "description": "Relire le code et exécuter les tests",
        },
        "security": {
            "keywords": ("sécurité", "sécuriser", "vulnérabilité", "authentification", "secret",
                         "security", "secure", "auth", "chiffrement", "données personnelles"),
            "agents": ("security",),
            "description": "Analyser les risques de sécurité",
        },
        "documentation": {
            "keywords": ("documenter", "documentation", "readme", "guide", "expliquer",
                         "document", "docs", "manuel"),
            "agents": ("documentation",),
            "description": "Mettre la documentation à jour",
        },
        "deployment": {
            "keywords": ("déployer", "déploiement", "production", "livrer", "release",
                         "deploy", "publish", "mise en ligne"),
            # `tester` accompagne le déploiement : préparer une mise en
            # production sans savoir si les tests passent, c'est très
            # exactement la vitesse préférée à la vérité que la constitution
            # écarte (VOLET 01, ch. 04). L'agent de déploiement lit d'ailleurs
            # ce verdict et rapporte `test_state.known: false` sans lui.
            "agents": ("tester", "deployment"),
            "description": "Vérifier l'état des tests, puis préparer la mise en production",
        },
        "monitoring": {
            "keywords": ("surveiller", "monitoring", "performance", "logs", "métriques",
                         "monitor", "observability", "alerte"),
            "agents": ("monitor",),
            "description": "Mettre en place le suivi d'exécution",
        },
    }

    # Plan appliqué quand aucune intention n'est reconnue : comprendre avant d'agir.
    #
    # `quality` en faisait partie, et cela devient coûteux dès que la
    # recommandation est suivie : une demande non reconnue — « bonjour » — faisait
    # exécuter toute la suite de tests du projet, soit 43 secondes pour vérifier
    # un code que personne n'avait produit. Comprendre une demande, c'est la
    # chercher, pas la tester.
    FALLBACK_INTENTS = ("research",)

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Construit le plan d'exécution de la demande.

        Args:
            context: Contexte d'exécution

        Returns:
            Objectif, intentions détectées, tâches ordonnées et contexte mobilisé
        """
        request = context.request_text()

        detected_intents = self._detect_intents(request)
        prior_knowledge = context.search_knowledge(request, limit=3)
        prior_memories = context.recall(request, limit=3)

        tasks = self._build_tasks(detected_intents, request)

        # Le plan est mémorisé pour que les agents suivants sachent ce qui est attendu d'eux
        context.remember(
            content={"objective": request, "tasks": tasks},
            memory_type="agent_shared",
            tags=["plan", "planner"],
        )

        return {
            "objective": request,
            "detected_intents": detected_intents,
            "task_count": len(tasks),
            "tasks": tasks,
            "agents_required": self._agents_for(detected_intents),
            "context_used": {
                "knowledge_items": len(prior_knowledge),
                "memories": len(prior_memories),
            },
            "model_assisted": self._try_model_refinement(context, request, tasks),
        }

    def _detect_intents(self, request: str) -> List[str]:
        """
        Repère les intentions présentes dans la demande.

        Deux défauts de la comparaison naïve sont corrigés ici, et ils sont
        devenus conséquents le jour où la recommandation a piloté l'exécution :
        une intention manquée ne coûte plus un agent inutile, elle coûte un
        agent absent.

        - **Les accents ne comptent pas.** « deploiement » est la façon dont on
          tape sur un clavier sénégalais ; sans normalisation, la demande
          perdait son intention de déploiement.
        - **Un mot-clé doit commencer un mot.** « veille » se trouvait dans
          « surveiller », si bien que toute demande de supervision déclenchait
          aussi une recherche. Le début de mot est exigé, la fin ne l'est pas :
          « application » reconnaît « applications ».
        """
        normalise = _sans_accents(request.lower())

        detected = [
            intent for intent, rule in self.INTENT_RULES.items()
            if any(_MOTIFS[keyword].search(normalise) for keyword in rule["keywords"])
        ]

        return detected or list(self.FALLBACK_INTENTS)

    def _agents_for(self, intents: List[str]) -> List[str]:
        """Retourne les agents mobilisés par les intentions, sans doublon."""
        agents: List[str] = []
        for intent in intents:
            for agent in self.INTENT_RULES[intent]["agents"]:
                if agent not in agents:
                    agents.append(agent)
        return agents

    def _build_tasks(self, intents: List[str], request: str) -> List[Dict[str, Any]]:
        """
        Construit les tâches à partir des intentions.

        Chaque tâche dépend de la précédente : le plan est séquentiel, ce qui
        reflète l'exécution réelle du pipeline.
        """
        tasks: List[Dict[str, Any]] = []

        # Parcourir INTENT_RULES et non `intents` garantit un ordre de phases stable
        for order, (intent, rule) in enumerate(self.INTENT_RULES.items()):
            if intent not in intents:
                continue

            task_id = f"task_{len(tasks) + 1}"
            tasks.append({
                "id": task_id,
                "intent": intent,
                "description": rule["description"],
                "assigned_agents": list(rule["agents"]),
                "depends_on": tasks[-1]["id"] if tasks else None,
                "priority": len(self.INTENT_RULES) - order,
            })

        return tasks

    def _try_model_refinement(self, context: AgentContext, request: str,
                              tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Demande au moteur de modèles d'affiner le plan, si un modèle est disponible.

        Le plan déterministe reste la référence : l'apport du modèle est un
        complément, jamais un remplacement. Sans modèle, l'agent produit le même
        plan et le signale, plutôt que de laisser croire à un raisonnement.
        """
        prompt = (
            f"Objectif: {request}\n"
            f"Plan proposé: {[task['description'] for task in tasks]}\n"
            "Indique les étapes manquantes."
        )
        outcome = context.generate(prompt, {"task_type": "planning"})

        return {
            "status": outcome.get("status"),
            "suggestion": outcome.get("text", ""),
            "reason": outcome.get("reason"),
        }


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Conservé pour que le dispatcher et les tests existants continuent de
    fonctionner sans contexte explicite.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(PlannerAgent, input_data)


# Motif par mot-clé : début de mot exigé, fin libre. Construits une fois — la
# détection tourne à chaque demande.
_MOTIFS = {
    mot: re.compile(r"\b" + re.escape(_sans_accents(mot)))
    for regle in PlannerAgent.INTENT_RULES.values()
    for mot in regle["keywords"]
}
