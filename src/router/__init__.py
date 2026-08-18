"""
Routeur : décide quel agent traite une requête, et dans quel ordre.

Responsabilités
    Charger les agents et les workflows déclarés, planifier leur exécution,
    les lancer, agréger leurs résultats et réessayer ce qui est réessayable.
    Le routeur ne contient aucune logique métier d'agent : il orchestre.

Interfaces publiques
    `RouterEngine` (`router_engine.py`) est le point d'entrée. Autour :
    `agent_loader` et `workflow_loader` lisent les déclarations,
    `execution_planner` construit le plan, `agent_dispatcher` exécute,
    `result_aggregator` rassemble, `retry_manager` reprend les échecs
    récupérables.

Dépendances
    Les registres déclaratifs `agents/agents.yaml` et
    `workflows/workflows.yaml`. Les moteurs sont obtenus par
    `src/integration/engine_registry.py`, jamais construits ici.

Configuration
    Aucune variable d'environnement propre : tout vient des fichiers de
    déclaration, ce qui permet d'ajouter un agent ou un workflow sans toucher
    au code.

Limites connues
    `execution_planner.py` est couvert à 58 % : les chemins de repli d'un plan
    partiellement exécutable ne sont pas tous éprouvés. Le workflow `standard`
    n'est jamais exécuté par la suite de tests — il contient l'agent `tester`,
    qui lancerait la suite à l'intérieur de la suite.
"""
