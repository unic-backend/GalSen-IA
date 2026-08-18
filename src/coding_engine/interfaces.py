"""
Contrat des adaptateurs de moteurs de codage (ADR-028).

GalSen IA dépend de **cette** interface, jamais des détails d'OpenHands, d'Aider
ou de SWE-agent. C'est ce qui permet de remplacer un moteur, ou d'en ajouter un
quatrième, sans réécrire le routeur, l'API ni les agents.

Un adaptateur promet trois choses :

- `check_availability()` répond **sans jamais lancer de tâche**, et le fait vite.
- `execute()` rend toujours un `CodingTaskResult`, y compris en cas de panne.
  Une exception qui remonte ferait tomber la requête d'un appelant qui n'a rien
  demandé d'autre qu'un statut.
- `capabilities` décrit ce que le moteur sait faire. Le routeur ne choisit que
  par là, jamais par nom : un moteur ajouté est routé sans que le routeur change.
"""

import abc
from typing import List, Optional

from src.coding_engine.types import (
    CodingCapability,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
)


class CodingEngineAdapter(abc.ABC):
    """Adaptateur vers un moteur d'ingénierie logicielle externe."""

    #: Identifiant stable, utilisé par la configuration et l'audit.
    engine_id: str = ""

    #: Nom lisible du moteur.
    display_name: str = ""

    #: Ce que le moteur sait faire ; base du routage.
    capabilities: List[CodingCapability] = []

    #: Ce que le moteur fait *le mieux*. Le routeur la pèse plus lourd que les
    #: autres capacités : « sait faire » et « fait le mieux » sont deux choses,
    #: et les confondre enverrait chaque tâche au moteur le plus polyvalent.
    primary_capability: Optional[CodingCapability] = None

    @abc.abstractmethod
    def check_availability(self) -> EngineAvailability:
        """
        Dit si le moteur peut travailler maintenant, et sinon pourquoi.

        L'appel doit être **rapide et sans effet** : il est fait à chaque
        interrogation de l'état de la plateforme. Il ne lance aucune tâche et
        n'écrit rien.

        Returns:
            L'état du moteur, avec le geste qui répare quand il manque.
        """

    @abc.abstractmethod
    def execute(self, task: CodingTask, model: Optional[ModelSpec]) -> CodingTaskResult:
        """
        Exécute une tâche et rend un résultat normalisé.

        Args:
            task: La tâche à exécuter. Son `workspace` a déjà été résolu et son
                instruction déjà examinée par le gestionnaire.
            model: Le modèle imposé par la plateforme. `None` signifie qu'aucun
                fournisseur n'est disponible : l'adaptateur doit alors rendre un
                résultat indisponible, jamais choisir un modèle de son côté.

        Returns:
            Le résultat, quel que soit le sort de l'exécution. Cette méthode ne
            lève pas : une panne est une donnée, pas une exception.
        """

    def supports(self, capabilities: List[CodingCapability]) -> bool:
        """
        Indique si le moteur couvre toutes les capacités demandées.

        Args:
            capabilities: Les capacités exigées par la tâche.

        Returns:
            Vrai si aucune ne manque.
        """
        return set(capabilities).issubset(set(self.capabilities))
