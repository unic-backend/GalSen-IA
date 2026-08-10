"""
Moteur de mémoire : ce que la plateforme retient d'une conversation à l'autre.

Responsabilités
    Stocker, retrouver, classer et résumer les souvenirs d'un utilisateur.
    Le moteur décide de la pertinence d'un souvenir ; il ne décide pas de ce
    qu'un agent en fait.

Interfaces publiques
    `MemoryManagerImpl` (`memory_manager.py`) est le point d'entrée : tout passe
    par lui. Les contrats sont dans `interfaces.py` (store, indexer, retriever,
    ranker, cache, summarizer) et chaque composant est remplaçable par
    injection. Les types échangés sont dans `types.py`.

Dépendances
    Aucune dépendance externe obligatoire. `src/storage/` fournit le magasin
    SQLite quand la persistance est activée.

Configuration
    `GALSEN_STORAGE_BACKEND` (`in-memory` par défaut, `sqlite` pour persister) et
    `GALSEN_DATA_DIR` (ADR-005).

Limites connues
    Le résumé de mémoire (`memory_summarizer.py`) et le classement
    (`memory_ranker.py`) sont peu couverts par les tests : ils dépendent d'un
    fournisseur de modèle, absent tant que le critère de sortie C1 n'est pas
    atteint. La mémoire n'est pas partagée entre instances (ADR-009).
"""
