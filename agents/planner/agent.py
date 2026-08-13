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
from src.knowledge_engine.scope import KnowledgeSubject
from src.text_normalization import strip_accents as _sans_accents


#: Marqueurs qui rattachent une demande au Sénégal (axe `geographic_scope`).
#: Villes et régions, pas seulement le nom du pays : « les prix à Kaolack » est
#: une question sénégalaise qui ne prononce jamais « Sénégal ».
MARQUEURS_SENEGAL = (
    "senegal", "senegalais", "dakar", "thies", "kaolack", "saint-louis",
    "ziguinchor", "casamance", "touba", "diourbel", "matam", "tambacounda",
    "louga", "fatick", "kolda", "kedougou", "sedhiou", "wolof", "pulaar",
    "serere", "cfa",
)

#: Sujets où une réponse fausse coûte plus qu'ailleurs, et leurs marqueurs.
#: L'axe `risk` en dépend, et il est l'un des deux qui agissent.
MARQUEURS_DE_RISQUE = {
    KnowledgeSubject.HEALTH.value: (
        "sante", "maladie", "traitement", "medicament", "symptome", "grossesse",
        "vaccin", "dosage", "paludisme", "diabete",
    ),
    KnowledgeSubject.LAW.value: (
        "droit", "loi", "legal", "juridique", "contrat", "tribunal", "foncier",
        "heritage", "succession", "licenciement", "amende",
    ),
    KnowledgeSubject.ECONOMICS.value: (
        "impot", "taxe", "credit", "pret", "investir", "salaire", "fiscal",
        "banque", "assurance",
    ),
}

#: Marqueurs qui exigent de l'information à jour (axe `freshness`).
MARQUEURS_DE_FRAICHEUR = (
    "actuel", "actuellement", "aujourd", "recent", "dernier", "derniere",
    "en vigueur", "maintenant", "2025", "2026", "cette annee",
)

#: Marqueurs de sujet (axe `domain`), rattachés aux valeurs de `KnowledgeSubject`.
#: Volontairement courts : cet axe est **observé**, pas branché, et une liste
#: longue donnerait l'illusion d'un classement fiable.
MARQUEURS_DE_SUJET = {
    KnowledgeSubject.AGRICULTURE.value: ("mil", "arachide", "culture", "semis", "recolte",
                                         "agricole", "agriculture", "elevage"),
    KnowledgeSubject.HEALTH.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.HEALTH.value],
    KnowledgeSubject.LAW.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.LAW.value],
    KnowledgeSubject.ECONOMICS.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.ECONOMICS.value],
    KnowledgeSubject.ADMINISTRATION.value: ("carte nationale", "passeport", "prefecture",
                                            "demarche", "administratif", "etat civil"),
    KnowledgeSubject.TECHNOLOGY.value: ("logiciel", "application", "api", "serveur",
                                        "code", "base de donnees"),
    KnowledgeSubject.EDUCATION.value: ("ecole", "universite", "scolaire", "eleve",
                                       "etudiant", "formation"),
    KnowledgeSubject.FISHERIES.value: ("peche", "pecheur", "piroque", "poisson"),
}

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

        axes = self._axes(request, detected_intents, prior_knowledge, context)
        agents, effets = self._agents_avec_axes(detected_intents, axes)

        return {
            "objective": request,
            "detected_intents": detected_intents,
            "task_count": len(tasks),
            "tasks": tasks,
            "agents_required": agents,
            # Les dix axes de la demande (VOLET 36, ch. F). Deux agissent, huit
            # sont observés — et `axes_effect` dit lequel a ajouté quel agent :
            # un axe qui changerait le routage sans se voir est exactement
            # ce qui rend un planificateur inexplicable.
            "axes": axes,
            "axes_effect": effets,
            "context_used": {
                "knowledge_items": len(prior_knowledge),
                "memories": len(prior_memories),
            },
            "model_assisted": self._try_model_refinement(context, request, tasks),
        }

    def _axes(self, request: str, intents: List[str], prior_knowledge: List[Any],
              context: AgentContext) -> Dict[str, Any]:
        """
        Décrit la demande selon les dix axes, chacun avec sa méthode.

        La méthode est rendue avec la valeur : `keywords` n'a pas la même valeur
        qu'une mesure, et `declared` encore moins qu'une détection. Un axe lu
        sans sa méthode passerait pour une observation dans les trois cas.
        """
        normalise = _sans_accents(request.lower())

        def present(marqueurs) -> bool:
            """Vraie si l'un des marqueurs commence un mot de la demande."""
            return any(_motif(marqueur).search(normalise) for marqueur in marqueurs)

        sujets = [
            sujet for sujet, marqueurs in MARQUEURS_DE_SUJET.items()
            if present(marqueurs)
        ]
        risques = [
            sujet for sujet, marqueurs in MARQUEURS_DE_RISQUE.items()
            if present(marqueurs)
        ]
        senegalais = present(MARQUEURS_SENEGAL)

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
                "value": "required" if present(MARQUEURS_DE_FRAICHEUR) else "unspecified",
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
                "assigned_agent": rule["agents"][0],
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


def _motif(mot: str) -> "re.Pattern":
    """Retourne le motif d'un marqueur, construit au premier usage."""
    motif = _MOTIFS.get(mot)
    if motif is None:
        motif = re.compile(r"\b" + re.escape(_sans_accents(mot)))
        _MOTIFS[mot] = motif
    return motif
