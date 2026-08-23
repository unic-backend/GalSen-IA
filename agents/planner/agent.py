"""
Planning Agent for GalSen IA.

Turns a request into an ordered task list. The decomposition is deterministic:
it comes from the intents detected in the request and from what the platform
already knows about it (memory and knowledge base), not from a language model.
The agent therefore produces the same plan for the same request, which is what
makes a plan reviewable.
"""

import re
from typing import Any, Dict, List, Tuple

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.markers import (
    MARQUEURS_DE_FRAICHEUR,
    contient,
    est_senegalais,
    sujets_a_risque,
    sujets_reperes,
)
from src.knowledge_engine.scope import KnowledgeSubject
from src.text_normalization import strip_accents as _sans_accents


# Les marqueurs de sujet, de pays, de risque et de fraîcheur vivent dans
# `src/knowledge_engine/markers.py` : le chapitre G leur a donné un second
# lecteur, et deux copies d'une même liste divergent.

#: L'agent que chacun des deux axes qui agissent recommande.
AGENT_PAR_AXE = {"risk": "verifier", "geographic_scope": "senegal"}

#: Axes rendus sans rien changer, le temps que leurs valeurs soient vues sur de
#: vraies demandes. Un axe branché avant d'avoir été lu est une décision que
#: personne n'a prise.
AXES_OBSERVES = (
    "domain", "task_type", "complexity", "freshness", "research_required",
    "tools_required", "execution_required", "language",
)


class PlannerAgent(BaseAgent):
    """Agent qui découpe une demande en tâches ordonnées."""

    agent_id = "planner"
    required_engines = ("memory", "knowledge", "model")

    # Intentions reconnues dans une demande, et agents qu'elles mobilisent.
    # L'ordre des clés fixe l'ordre des phases du plan.
    INTENT_RULES = {
        # Un échange de conversation n'a rien à chercher. Mesuré le 2026-08-23 :
        # « bonjour » traversait le `researcher` pendant **1 095 ms** pour
        # constater qu'il n'existe aucune source sur une salutation. C'est le
        # même défaut que `quality` dans le repli, un cran plus loin — et le
        # commentaire de `FALLBACK_INTENTS` en garde la trace.
        #
        # Aucun agent : la couche de réponse répond depuis le message et
        # l'historique. Ce n'est pas un contournement de l'orchestrateur, c'est
        # un plan qui ne mobilise personne.
        "conversation": {
            "keywords": ("bonjour", "bonsoir", "salut", "nanga def", "hello",
                         "merci", "au revoir", "a bientot", "ca va"),
            "agents": (),
            "description": "Répondre à un échange, sans rien chercher",
        },
        "research": {
            "keywords": ("recherche", "rechercher", "étudier", "analyser le marché", "veille",
                         "research", "investigate", "explore", "étude", "comparer"),
            "agents": ("researcher",),
            "description": "Rassembler et vérifier l'information nécessaire",
        },
        "implementation": {
            "keywords": ("développer", "créer", "implémenter", "coder", "construire", "ajouter",
                         "build", "implement", "develop", "create", "application", "fonctionnalité",
                         # Mesuré le 2026-08-23 : « Écris une fonction Python »
                         # tombait sur `research`, à l'identique de « Explique
                         # Linux », et n'atteignait jamais le moteur de codage.
                         # Les motifs restent composés à dessein : « écris » seul
                         # attraperait « écris-moi un poème », qui n'a rien à
                         # faire chez le `coder`.
                         "écris une fonction", "écrire une fonction",
                         "écris un script", "écrire un script",
                         "écris du code", "écrire du code",
                         "write a function", "write a script", "write code"),
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
            "keywords": ("sécurité", "sécuris", "vulnérabilité", "authentification", "secret",
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

    # Au-delà, ce n'est plus un échange : c'est une demande qui commence
    # poliment. Six mots laissent passer « bonjour, comment vas-tu ? » et
    # arrêtent « bonjour, peux-tu m'expliquer la relativité générale ».
    MOTS_MAX_CONVERSATION = 6

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

        # 1. Détecter l'intention avant d'appeler les moteurs coûteux.
        detected_intents = self._detect_intents(request)

        # 2. Une conversation simple ne nécessite ni recherche de connaissances
        # ni recherche mémoire.
        if detected_intents == ["conversation"]:
            prior_knowledge = []
            prior_memories = []
        else:
            prior_knowledge = context.search_knowledge(request, limit=3)
            prior_memories = context.recall(request, limit=3)

        tasks = self._build_tasks(detected_intents, request)

        # 3. Une conversation simple ne produit aucune tâche pour les agents.
        # Il est donc inutile de l'enregistrer comme plan partagé.
        if detected_intents != ["conversation"]:
            context.remember(
                content={"objective": request, "tasks": tasks},
                memory_type="agent_shared",
                tags=["plan", "planner"],
            )

        axes = self._axes(
            request,
            detected_intents,
            prior_knowledge,
            context,
        )

        agents, effets = self._agents_avec_axes(
            detected_intents,
            axes,
        )

        # 4. Le raffinement par modèle est inutile pour une conversation simple.
        if detected_intents == ["conversation"]:
            model_assisted = {
                "status": "skipped",
                "suggestion": "",
                "reason": "Raffinement modèle inutile pour une conversation simple.",
            }
        else:
            model_assisted = self._try_model_refinement(
                context,
                request,
                tasks,
            )

        return {
            "objective": request,
            "detected_intents": detected_intents,
            "task_count": len(tasks),
            "tasks": tasks,
            "agents_required": agents,
            "axes": axes,
            "axes_effect": effets,
            "context_used": {
                "knowledge_items": len(prior_knowledge),
                "memories": len(prior_memories),
            },
            "model_assisted": model_assisted,
        }
    
    def _axes(self, request: str, intents: List[str], prior_knowledge: List[Any],
              context: AgentContext) -> Dict[str, Any]:
        """
        Décrit la demande selon les dix axes, chacun avec sa méthode.

        La méthode est rendue avec la valeur : `keywords` n'a pas la même valeur
        qu'une mesure, et `declared` encore moins qu'une détection. Un axe lu
        sans sa méthode passerait pour une observation dans les trois cas.
        """
        sujets = sujets_reperes(request)
        risques = sujets_a_risque(request)
        senegalais = est_senegalais(request)

        return {
            "domain": {
                "value": sujets or [KnowledgeSubject.UNSPECIFIED.value],
                "method": "keywords",
            },
            # Déjà produit par `INTENT_RULES` : l'axe le nomme, il ne le recalcule pas.
            "task_type": {"value": list(intents), "method": "intent_rules"},
            "complexity": {
                "value": self._complexite(intents, request),
                "method": "crude",
                "note": (
                    "Nombre d'intentions et longueur de la demande. C'est grossier "
                    "et rendu comme tel : ce n'est pas une estimation d'effort."
                ),
            },
            "risk": {
                "value": "elevated" if risques else "ordinary",
                "subjects": risques,
                "method": "keywords",
                "note": (
                    "Santé, droit et argent : une réponse fausse y coûte plus "
                    "qu'ailleurs."
                ),
            },
            "freshness": {
                "value": ("required" if contient(request, MARQUEURS_DE_FRAICHEUR)
                          else "unspecified"),
                "method": "keywords",
            },
            "research_required": {
                # Mesure, pas mot-clé : la base ne porte rien sur cette demande.
                "value": not prior_knowledge,
                "method": "measured",
                "knowledge_items": len(prior_knowledge),
            },
            "tools_required": {
                "value": self._agents_for(intents),
                "method": "implied_by_agents",
            },
            "execution_required": {
                "value": bool({"implementation", "deployment"} & set(intents)),
                "method": "intent_rules",
            },
            "language": {
                # **Déclarée, pas détectée** : aucun détecteur n'existe dans le
                # dépôt (VOLET 36, ch. B — `language_support()` le dit).
                "value": str(context.options.get("language") or "fr"),
                "method": "declared",
                "detected": False,
            },
            "geographic_scope": {
                "value": "country:sn" if senegalais else "global",
                "method": "keywords",
            },
        }

    def _agents_avec_axes(self, intents: List[str],
                          axes: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Ajoute les agents que deux axes recommandent, et dit lequel les a ajoutés.

        Seuls `risk` et `geographic_scope` agissent. Les huit autres sont
        observés le temps que leurs valeurs soient vues sur de vraies demandes :
        un axe branché avant d'avoir été lu est une décision que personne n'a
        prise.

        La recommandation reste une recommandation : `workflows.yaml` garde
        l'autorité sur ce qui **peut** tourner, et un agent recommandé mais non
        déclaré n'entre pas dans l'exécution.
        """
        agents = self._agents_for(intents)
        effets = []
        for axe, declencheur, agent in (
            ("risk", "elevated", AGENT_PAR_AXE["risk"]),
            ("geographic_scope", "country:sn", AGENT_PAR_AXE["geographic_scope"]),
        ):
            if axes[axe]["value"] != declencheur:
                continue
            effets.append({"axis": axe, "value": declencheur, "agent_added": agent})
            if agent not in agents:
                agents.append(agent)
        return agents, effets

    @staticmethod
    def _complexite(intents: List[str], request: str) -> str:
        """
        Estime grossièrement l'ampleur d'une demande.

        Deux signaux seulement — combien d'intentions, quelle longueur. Ni l'un
        ni l'autre ne mesure une difficulté ; les additionner ne la mesure pas
        davantage, et c'est pourquoi la valeur reste une étiquette sans chiffre.
        """
        signaux = len(intents) + (1 if len(request) > 280 else 0)
        if signaux >= 3:
            return "high"
        return "moderate" if signaux == 2 else "low"

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

        # `conversation` ne s'ajoute jamais aux autres intentions : « bonjour,
        # explique-moi la relativité » est une question, pas une salutation. Et
        # une salutation reste une salutation seulement si elle est brève —
        # sans cette borne, un long message commençant par « bonjour » perdrait
        # sa recherche, ce qui est le défaut inverse de celui qu'on corrige.
        if "conversation" in detected:
            autres = [i for i in detected if i != "conversation"]
            if autres or len(normalise.split()) > self.MOTS_MAX_CONVERSATION:
                detected = autres

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
                # Premier agent de la phase : c'est lui qui porte la tâche. Le
                # champ existe pour que `context.tasks_for()` réponde sans avoir
                # à connaître la forme du plan.
                #
                # `None` quand l'intention ne mobilise personne — le cas de
                # `conversation`, où il n'y a rien à faire exécuter. Indexer un
                # tuple vide levait `IndexError` et faisait tomber le planner
                # tout entier : une intention sans agent est un plan valide,
                # pas une panne.
                "assigned_agent": rule["agents"][0] if rule["agents"] else None,
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

