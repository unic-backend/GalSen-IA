"""
Analytique : ce que la plateforme a fait, agrégé en indicateurs lisibles.

Responsabilités
    Rassembler les mesures que les autres moteurs produisent déjà — audit,
    historique des workflows, compteurs HTTP et de recherche — et les présenter
    comme un seul état. Ce paquet **ne collecte rien** : ajouter une deuxième
    collecte à côté de l'audit ferait diverger deux vérités sur les mêmes
    exécutions.

Interfaces publiques
    `build_report()` produit le rapport complet ; `source_coverage()` dit
    lesquelles des sources de données du VOLET 09 chapitre 04 sont réellement
    branchées.

Dépendances
    Aucune obligatoire : chaque source est optionnelle et son absence est
    rapportée comme telle plutôt que de faire échouer le rapport.

Configuration
    Aucune variable d'environnement propre.

Limites connues
    Il n'y a **pas de stockage analytique** : tout ce qui est agrégé vit en
    mémoire du processus (ADR-009) et disparaît au redémarrage. Aucune tendance
    ni détection d'anomalie n'est donc calculée — elles demandent une série
    temporelle conservée, que rien ne conserve.
"""

from .reporter import build_report, source_coverage, UNAVAILABLE_CAPABILITIES

__all__ = ["build_report", "source_coverage", "UNAVAILABLE_CAPABILITIES"]
