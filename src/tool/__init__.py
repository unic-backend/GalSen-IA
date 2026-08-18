"""
Moteur d'outils : charge les outils déclarés et les exécute pour un agent.

Responsabilités
    Lire le registre d'outils, instancier ce qui est activé, valider les
    arguments d'un appel et exécuter l'opération demandée. Le moteur ne sait
    rien de ce que fait un outil : il applique un contrat.

Interfaces publiques
    `ToolEngine` (`tool_engine.py`) est le point d'entrée. `BaseTool`
    (`base.py`) est le contrat que tout outil implémente — c'est ce qui rend un
    outil remplaçable. `tool_loader.py` lit le registre, `tool_executor.py`
    exécute.

Dépendances
    Le registre `tools/tools.yaml`. Les outils eux-mêmes vivent dans
    `src/tools/` et déclarent leurs propres dépendances, souvent optionnelles.

Configuration
    Le chemin du registre est passé à la construction. Chaque outil lit ses
    propres réglages (jetons, URL) dans l'environnement, décrits par
    `.env.example`.

Limites connues
    Un outil dont la dépendance optionnelle manque reste déclaré et rapporte
    son indisponibilité à l'appel : il ne disparaît pas du registre, pour qu'un
    opérateur voie ce que l'installation saurait faire une fois complétée.
"""
