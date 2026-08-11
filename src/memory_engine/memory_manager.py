"""
Gestionnaire de mémoire pour GalSen IA.

L'interface principale pour les agents afin d'interagir avec le système de mémoire.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from .types import MemoryItem, MemoryType, MemoryPriority, MemoryStatus
from .interfaces import (
    MemoryStore, MemoryRetriever, MemoryIndexer,
    MemorySummarizer, MemoryRanker, MemoryCache, MemoryManager as MemoryManagerInterface
)
from .memory_quality import DEFAULT_INACTIVITY_DAYS, inactive_memories, quality_report
from .memory_store import InMemoryMemoryStore
from .memory_retriever import InMemoryMemoryRetriever
from .memory_indexer import InMemoryMemoryIndexer
from .memory_cache import LRUMemoryCache
from .memory_summarizer import SimpleMemorySummarizer
from .memory_ranker import SimpleMemoryRanker
from src.storage.sqlite_store import SQLiteMemoryStore
from src.storage.paths import storage_backend


class MemoryManager(MemoryManagerInterface):
    """
    Gestionnaire principal de mémoire qui coordonne toutes les opérations de mémoire.

    Cette classe implémente l'interface MemoryManagerInterface et utilise les divers
    composants de mémoire pour fournir une API unifiée aux agents.
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        """Initialiser le gestionnaire de mémoire.

        Args:
            store: Magasin de mémoire optionnel à utiliser. Si non fourni, le magasin est déterminé par la
                   variable d'environnement GALSEN_STORAGE_BACKEND (valeurs : "in-memory" ou "sqlite").
                   Par défaut à "in-memory".
        """
        self._logger = logging.getLogger(__name__)
        # Initialiser les composants
        if store is None:
            storage_type = storage_backend()
            if storage_type == "sqlite":
                self._store: MemoryStore = SQLiteMemoryStore()
            else:
                self._store: MemoryStore = InMemoryMemoryStore()
        else:
            self._store: MemoryStore = store
        self._retriever: MemoryRetriever = InMemoryMemoryRetriever(self._store)
        self._indexer: MemoryIndexer = InMemoryMemoryIndexer()
        self._cache: MemoryCache = LRUMemoryCache(max_size=1000)
        self._summarizer: MemorySummarizer = SimpleMemorySummarizer()
        self._ranker: MemoryRanker = SimpleMemoryRanker()
        store_type = "in-memory" if store is None else "custom"
        if store is None:
            store_type = storage_backend()
        self._logger.info(f"MemoryManager initialisé avec des composants {store_type}.")

    # Note : Dans un système de production, nous autoriserions l'injection de dépendance
    # de ces composants pour permettre différents backends (par exemple, SQL, base de données vectorielle).

    def save_memory(self, item: MemoryItem) -> str:
        """Sauver un élément de mémoire.

        Args:
            item: L'élément de mémoire à sauver.

        Returns:
            L'ID de l'élément sauvegardé.
        """
        self._logger.debug(f"Sauvegarde de l'élément de mémoire : {item.id}")
        # Indexer l'élément avant la sauvegarde (ou après, mais nous le faisons avant pour qu'il soit indexé)
        self._indexer.index(item)
        item_id = self._store.save(item)
        # Mettre en cache l'élément par son ID pour une récupération rapide
        self._cache.set(f"item:{item_id}", item, ttl=3600)  # Cache pour 1 heure
        return item_id

    def get_memory(self, item_id: str) -> Optional[MemoryItem]:
        """Récupérer un élément de mémoire par son ID.

        Args:
            item_id: L'ID de l'élément à récupérer.

        Returns:
            L'élément de mémoire trouvé, sinon None.
        """
        self._logger.debug(f"Récupération de l'élément de mémoire : {item_id}")
        # Essayer le cache en premier
        cached = self._cache.get(f"item:{item_id}")
        if cached is not None:
            # Une mémoire expirée ne doit pas être servie parce qu'elle a été lue
            # récemment : le cache survivait au nettoyage et rendait un souvenir
            # que la politique de rétention avait effacé (VOLET 07, ch. 03).
            if self._is_expired(cached):
                self._cache.delete(f"item:{item_id}")
                return None
            return cached
        # Si pas dans le cache, obtenir depuis le magasin
        item = self._store.get(item_id)
        if item is not None and self._is_expired(item):
            return None
        if item is not None:
            # Le mettre en cache
            self._cache.set(f"item:{item_id}", item, ttl=3600)
        return item

    @staticmethod
    def _is_expired(item: MemoryItem) -> bool:
        """Indique si une mémoire a dépassé sa date d'expiration.

        L'expiration est déclarée par l'appelant : la respecter à la lecture est
        ce qui la rend réelle. S'en remettre au seul `cleanup_expired()` faisait
        dépendre une règle de rétention du passage d'une tâche de ménage.
        """
        return item.expires_at is not None and item.expires_at < time.time()

    def update_memory(self, item: MemoryItem) -> bool:
        """Mettre à jour un élément de mémoire.

        Args:
            item: L'élément de mémoire avec du contenu mis à jour.

        Returns:
            True si mis à jour, False sinon.
        """
        self._logger.debug(f"Mise à jour de l'élément de mémoire : {item.id}")
        # Mettre à jour dans le magasin
        updated = self._store.update(item)
        if updated:
            # Mettre à jour l'index
            self._indexer.update_index(item)
            # Mettre à jour le cache
            self._cache.set(f"item:{item.id}", item, ttl=3600)
        return updated

    def delete_memory(self, item_id: str) -> bool:
        """Supprimer un élément de mémoire par son ID.

        Args:
            item_id: L'ID de l'élément à supprimer.

        Returns:
            True si supprimé, False sinon.
        """
        self._logger.debug(f"Suppression de l'élément de mémoire : {item_id}")
        # Supprimer du magasin
        deleted = self._store.delete(item_id)
        if deleted:
            # Désindexer
            self._indexer.deindex(item_id)
            # Supprimer du cache
            self._cache.delete(f"item:{item_id}")
        return deleted

    def search_memory(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Tuple[MemoryItem, float]]:
        """Rechercher les mémoires pertinentes par rapport à une requête.

        Args:
            query: La requête de recherche.
            memory_type: Filtrer par type de mémoire.
            user_id: Filtrer par ID utilisateur.
            session_id: Filtrer par ID de session.
            agent_id: Filtrer par ID d'agent.
            tags: Filtrer par tags.
            limit: Nombre maximum de résultats.

        Returns:
            Liste de tuples (élément de mémoire, score de pertinence).
        """
        self._logger.debug(f"Recherche de mémoire avec la requête : {query}")
        # Utiliser le récupérateur pour obtenir les éléments et les scores
        results = self._retriever.retrieve(
            query=query,
            memory_type=memory_type,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            tags=tags,
            limit=limit
        )
        # Optionnellement, nous pourrions classer les résultats à nouveau, mais le récupérateur les note déjà
        return results

    def forget_memory(self, item_id: str) -> bool:
        """Oublier un élément de mémoire : il est archivé, pas effacé.

        Le chapitre 03 distingue l'archivage (étape 7) de la suppression
        (étape 8), et le statut `ARCHIVED` existait sans que rien ne le pose.
        « Oublier » supprimait donc définitivement, ce qu'aucun appelant
        n'attendait d'un verbe aussi doux — et ce que la politique de rétention
        interdit tant qu'une mémoire n'est pas obsolète.

        Une mémoire archivée n'est plus retournée par la recherche ; elle reste
        lisible par son identifiant, et `delete_memory()` l'efface pour de bon.

        Args:
            item_id: L'ID de l'élément à oublier.

        Returns:
            True si l'élément a été archivé, False s'il n'existe pas.
        """
        self._logger.debug(f"Archivage de l'élément de mémoire : {item_id}")
        item = self._store.get(item_id)
        if item is None:
            return False

        item.status = MemoryStatus.ARCHIVED
        item.updated_at = time.time()
        if not self._store.update(item):
            return False

        # Retirée de l'index : une mémoire archivée ne remonte plus dans une
        # recherche, sans quoi l'archivage ne changerait rien à l'usage.
        self._indexer.deindex(item_id)
        self._cache.set(f"item:{item_id}", item, ttl=3600)
        return True

    def deduplicate(self, user_id: Optional[str] = None,
                    dry_run: bool = False) -> Dict[str, Any]:
        """
        Archive les mémoires en double, en gardant la plus ancienne de chaque groupe.

        Le chapitre 03 du VOLET 20 range « supprimer les connaissances en
        double » parmi ses pratiques de gestion, et la détection parmi ses
        contrôles qualité. Seule la détection existait : `quality_report()`
        annonçait « 2 éléments redondants » et rien ne pouvait agir dessus.
        Mesuré, trois enregistrements du même contenu produisaient trois
        mémoires **et la recherche rendait les trois** — l'appelant recevait
        trois fois la même réponse et le contexte de l'agent s'en trouvait
        rempli de répétitions.

        Deux mémoires sont considérées identiques quand le propriétaire et le
        contenu textuel coïncident, après retrait des espaces de bord. C'est
        exactement le critère de `quality_report()` : deux définitions
        différentes du doublon donneraient un rapport et une action en désaccord.

        La **plus ancienne est conservée** : elle porte la date à laquelle la
        connaissance est apparue. Les autres sont **archivées, pas supprimées**
        — même distinction que `forget_memory()`, et la même raison : rien
        n'autorise à effacer ce qu'un utilisateur a enregistré au motif qu'il
        l'a enregistré deux fois.

        Args:
            user_id: se limiter aux mémoires d'un propriétaire.
            dry_run: ne rien modifier et rapporter ce qui serait archivé.

        Returns:
            Le nombre de groupes trouvés, le nombre de mémoires archivées et
            leurs identifiants.
        """
        try:
            items = self._store.list_items(limit=100000)
        except Exception as error:
            self._logger.warning("Déduplication impossible : %s", error)
            return {"groups": 0, "archived": 0, "archived_ids": [], "dry_run": dry_run}

        groupes: Dict[Any, List[MemoryItem]] = {}
        for item in items:
            if item.status != MemoryStatus.ACTIVE or not isinstance(item.content, str):
                continue
            if user_id is not None and item.user_id != user_id:
                continue
            groupes.setdefault((item.user_id, item.content.strip()), []).append(item)

        a_archiver: List[str] = []
        groupes_avec_doublon = 0
        for lot in groupes.values():
            if len(lot) < 2:
                continue
            groupes_avec_doublon += 1
            # La plus ancienne d'abord ; `created_at` peut manquer sur une
            # mémoire ancienne, auquel cas elle est traitée comme la plus vieille.
            lot.sort(key=lambda i: i.created_at or 0.0)
            a_archiver.extend(item.id for item in lot[1:] if item.id)

        archivees = []
        if not dry_run:
            archivees = [item_id for item_id in a_archiver if self.forget_memory(item_id)]

        return {
            "groups": groupes_avec_doublon,
            "archived": len(a_archiver) if dry_run else len(archivees),
            "archived_ids": a_archiver if dry_run else archivees,
            "dry_run": dry_run,
        }

    def consolidate_memory(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Consolider les mémoires (par exemple, déplacer le court terme vers le long terme, résumer).

        Args:
            user_id: Consolider pour un utilisateur spécifique (None pour tous).
            session_id: Consolider pour une session spécifique (None pour toutes).

        Returns:
            Nombre de mémoires traitées.
        """
        self._logger.warning(
            "consolidate_memory() n'est pas implémentée : aucune mémoire n'a été "
            "consolidée pour l'utilisateur %s (session %s).", user_id, session_id
        )
        raise NotImplementedError(
            "La consolidation de mémoire n'est pas implémentée. Elle demande de "
            "décider ce qui passe du court au long terme, ce qui se résume et "
            "selon quelle courbe d'oubli — aucune de ces règles n'existe encore. "
            "Retourner 0 laissait croire qu'il n'y avait rien à consolider."
        )

    def quality_report(self, max_age_days: int = None) -> Dict[str, Any]:
        """
        Rapporte la qualité et la rétention des mémoires (chapitres 08 et 09).

        Args:
            max_age_days: seuil d'inactivité en jours ; le défaut du module sinon

        Returns:
            Fraîcheur, doublons, complétude des métadonnées, répartition par
            statut et par type, mémoires inactives à revoir, et les métriques que
            la plateforme ne sait pas calculer avec leur raison.
        """
        if max_age_days is None:
            return quality_report(self._store)
        return quality_report(self._store, max_age_days=max_age_days)

    def list_inactive(self, max_age_days: int = DEFAULT_INACTIVITY_DAYS) -> List[MemoryItem]:
        """
        Liste les mémoires actives que personne n'a touchées depuis longtemps.

        Répond à « revoir les mémoires inactives » (chapitre 08). Rien n'est
        archivé automatiquement : retirer une mémoire de l'usage est une décision,
        pas un effet de bord d'un rapport.
        """
        return inactive_memories(self._store.list_items(limit=100000), max_age_days)

    def cleanup_expired(self) -> int:
        """Supprimer les mémoires expirées.

        Returns:
            Nombre de mémoires supprimées.
        """
        self._logger.debug("Nettoyage des mémoires expirées")
        supprimees = self._store.cleanup_expired()
        if supprimees:
            # Sans cette purge, une mémoire supprimée du magasin restait servie
            # par le cache : le nettoyage rapportait un nombre exact et la
            # mémoire était toujours lisible.
            self._cache.clear()
        return supprimees

    # Méthodes supplémentaires qui pourraient être utiles mais ne font pas partie de l'interface
    def get_store(self) -> MemoryStore:
        """Obtenir le magasin de mémoire (pour une utilisation avancée)."""
        return self._store

    def get_retriever(self) -> MemoryRetriever:
        """Obtenir le récupérateur de mémoire (pour une utilisation avancée)."""
        return self._retriever

    def get_indexer(self) -> MemoryIndexer:
        """Obtenir l'indexeur de mémoire (pour une utilisation avancée)."""
        return self._indexer

    def get_cache(self) -> MemoryCache:
        """Obtenir le cache de mémoire (pour une utilisation avancée)."""
        return self._cache

    def get_summarizer(self) -> MemorySummarizer:
        """Obtenir le résumeur de mémoire (pour une utilisation avancée)."""
        return self._summarizer

    def get_ranker(self) -> MemoryRanker:
        """Obtenir le classeur de mémoire (pour une utilisation avancée)."""
        return self._ranker