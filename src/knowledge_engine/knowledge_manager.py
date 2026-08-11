"""
Gestionnaire principal du moteur de connaissances GalSen IA.
"""

from typing import Iterable, List, Dict, Any, Optional, Tuple
from .types import KnowledgeItem, KnowledgeSource, KnowledgePriority, KnowledgeStatus
from .knowledge_lifecycle import check_transition, is_due_for_revalidation, is_retrievable
from .knowledge_governance import governance_report
from .knowledge_security import can_read
from .knowledge_quality import quality_report
from .interfaces import (
    KnowledgeStore, KnowledgeLoader, KnowledgeIndexer,
    KnowledgeRetriever, KnowledgeValidator, KnowledgeGraph,
    KnowledgeCache, KnowledgeRanker, KnowledgeManager
)
from .knowledge_store import InMemoryKnowledgeStore
from .knowledge_loader import KnowledgeLoaderFactory
from .knowledge_indexer import InMemoryKnowledgeIndexer
from .knowledge_retriever import KnowledgeRetrieverImpl
from .knowledge_validator import KnowledgeValidatorImpl
from .knowledge_graph import InMemoryKnowledgeGraph
from .knowledge_cache import TTLCache
from .knowledge_ranker import KnowledgeRankerImpl
import copy
import datetime
import logging
import threading
import os


class KnowledgeManagerImpl(KnowledgeManager):
    """
    Implémentation concrète du gestionnaire de connaissances qui coordonne
    tous les composants du moteur de connaissances.
    """

    def __init__(self,
                 store: Optional[KnowledgeStore] = None,
                 loader: Optional[KnowledgeLoader] = None,
                 indexer: Optional[KnowledgeIndexer] = None,
                 retriever: Optional[KnowledgeRetriever] = None,
                 validator: Optional[KnowledgeValidator] = None,
                 graph: Optional[KnowledgeGraph] = None,
                 cache: Optional[KnowledgeCache] = None,
                 ranker: Optional[KnowledgeRanker] = None):
        """
        Initialise le gestionnaire de connaissances.

        Args:
            store: Stockage des connaissances (par défaut: InMemoryKnowledgeStore)
            loader: Chargeur de connaissances (par défaut: KnowledgeLoaderFactory)
            indexer: Indexeur de connaissances (par défaut: InMemoryKnowledgeIndexer)
            retriever: Récupérateur de connaissances (par défaut: KnowledgeRetrieverImpl)
            validator: Validateur de connaissances (par défaut: KnowledgeValidatorImpl)
            graph: Graphe de connaissances (par défaut: InMemoryKnowledgeGraph)
            cache: Cache de connaissances (par défaut: TTLCache)
            ranker: Classeur de connaissances (par défaut: KnowledgeRankerImpl)
        """
        # Composants avec valeurs par défaut
        if store is not None:
            self._store = store
        elif os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").lower() == "sqlite":
            # Import différé pour éviter un import circulaire avec storage.
            from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore
            self._store = SQLiteKnowledgeStore()
        else:
            self._store = InMemoryKnowledgeStore()
        self._loader = loader or KnowledgeLoaderFactory
        self._indexer = indexer or InMemoryKnowledgeIndexer(self._store)
        self._retriever = retriever or KnowledgeRetrieverImpl(self._indexer)
        self._validator = validator or KnowledgeValidatorImpl()
        self._graph = graph or InMemoryKnowledgeGraph()
        self._cache = cache or TTLCache(maxsize=1000, ttl=300.0)  # 5 min TTL par défaut
        self._ranker = ranker or KnowledgeRankerImpl()

        self._logger = logging.getLogger(__name__)
        self._logger.info("Gestionnaire de connaissances initialisé")

        # Verrou pour les opérations qui nécessitent de la cohérence entre composants
        self._lock = threading.RLock()

    # Méthodes de gestion des connaissances
    def add_knowledge(self, knowledge: KnowledgeItem) -> str:
        """
        Ajoute une connaissance à la base.

        Returns:
            ID de la connaissance ajoutée
        """
        with self._lock:
            # Valider la connaissance
            is_valid, errors = self.validate_knowledge(knowledge)
            if not is_valid:
                raise ValueError(f"Knowledge validation failed: {', '.join(errors)}")

            # Vérifier les doublons exacts (optionnel)
            existing = self._store.list_items()
            warnings = self._validator.check_consistency(knowledge, existing)
            if warnings:
                for w in warnings:
                    self._logger.warning(f"Knowledge consistency warning: {w}")

            # Sauvegarder dans le stockage
            kid = self._store.save(knowledge)

            # Ajouter au graphe (en tant que nœud isolé pour l'instant)
            self._graph.add_node(kid)

            # Mettre à jour les métadonnées d'accès initiale
            km = self._store.get(kid)
            if km:
                km.metadata.setdefault("access_count", 0)
                self._store.update(km)  # incrémentera la version

            # Indexer et mettre en cache **ce que le magasin détient**, jamais ce
            # qui lui a été soumis.
            #
            # `KnowledgeStore.save()` refuse une écriture quand une version au
            # moins aussi récente existe sous le même identifiant, et il le fait
            # en retournant cet identifiant : « créé », « inchangé » et
            # « refusé » sont indiscernables pour l'appelant. Mettre en cache
            # l'objet soumis faisait alors diverger trois vues d'une même
            # connaissance — mesuré avant correction, `get_knowledge()` rendait
            # « Le mil se sème en juillet. » pendant que le magasin et la
            # recherche rendaient « ... en juin. ». Le chapitre 03 du VOLET 21
            # range la validation d'intégrité et la cohérence parmi ses
            # contrôles qualité ; un cache qui contredit son magasin les défait
            # tous les deux.
            stocke = km or knowledge
            if km is not None and km.compute_content_hash() != knowledge.compute_content_hash():
                self._logger.warning(
                    "Connaissance non écrite : l'identifiant %s porte déjà une version "
                    "au moins aussi récente. Le contenu soumis a été ignoré ; "
                    "utilisez update_knowledge() pour corriger une connaissance existante.",
                    kid,
                )
            self._indexer.add(stocke)
            self._cache.set(f"knowledge:{kid}", stocke)
            self._invalidate_query_cache()

            self._logger.debug(f"Knowledge added with ID: {kid}")
            return kid

    # Préfixe des entrées de cache portant un résultat de recherche.
    _QUERY_CACHE_PREFIX = "query:"

    def _cached_search(self, cle: str, producteur) -> List[Tuple[KnowledgeItem, float]]:
        """
        Sert un résultat de recherche depuis le cache, ou le produit et le garde.

        Répond à « Cache frequent queries » (chapitre 05, PERFORMANCE). Le
        producteur n'est appelé qu'en cas d'absence : tout ce qu'il coûte — y
        compris la lecture complète du magasin — n'est payé qu'une fois.
        """
        cached = self._cache.get(cle)
        if cached is not None:
            return list(cached)

        resultats = [(k, s) for k, s in producteur() if k is not None]
        self._cache.set(cle, list(resultats))
        return resultats

    def _search_index(self, query: str, limit: int) -> List[Tuple[KnowledgeItem, float]]:
        """Interroge l'index. La clé porte la limite : deux limites ne partagent
        pas un résultat tronqué."""
        return self._cached_search(
            f"{self._QUERY_CACHE_PREFIX}index:{limit}:{query}",
            lambda: self._indexer.search(query, limit=limit),
        )

    def _retrieve_relevant(self, prompt: str, limit: int) -> List[Tuple[KnowledgeItem, float]]:
        """Passe par le récupérateur injecté — remplaçable — avec le même cache."""
        return self._cached_search(
            f"{self._QUERY_CACHE_PREFIX}rag:{limit}:{prompt}",
            lambda: self._retriever.retrieve_relevant(
                prompt, self._store.list_items(limit=10000), limit=limit),
        )

    def _invalidate_query_cache(self) -> None:
        """
        Vide les résultats de recherche mis en cache.

        Appelé à chaque écriture : un résultat périmé est pire qu'un cache vide,
        il fait disparaître une connaissance qui vient d'être ajoutée.
        """
        for cle in self._cache.keys():
            if cle.startswith(self._QUERY_CACHE_PREFIX):
                self._cache.delete(cle)

    def get_store(self):
        """
        Retourne le stockage de connaissances sous-jacent.

        Returns:
            Instance du KnowledgeStore utilisé
        """
        return self._store

    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """
        Récupère une connaissance par son ID.

        Returns:
            KnowledgeItem ou None si non trouvé
        """
        # Vérifier le cache d'abord
        cached = self._cache.get(f"knowledge:{knowledge_id}")
        if cached is not None:
            # Incrémenter le compteur d'accès
            self._increment_access_count(knowledge_id)
            return cached

        # Sinon, lire depuis le stockage
        with self._lock:
            knowledge = self._store.get(knowledge_id)
            if knowledge:
                # Mettre en cache
                self._cache.set(f"knowledge:{knowledge_id}", knowledge)
                # Incrémenter le compteur d'accès
                self._increment_access_count(knowledge_id)
            return knowledge

    def update_knowledge(self, knowledge: KnowledgeItem) -> bool:
        """
        Met à jour une connaissance existante.

        Returns:
            True si la mise à jour a réussi, False sinon
        """
        with self._lock:
            # Valider la connaissance mise à jour
            is_valid, errors = self.validate_knowledge(knowledge)
            if not is_valid:
                raise ValueError(f"Knowledge validation failed: {', '.join(errors)}")

            # Vérifier que l'original existe
            existing = self._store.get(knowledge.id)
            if not existing:
                return False

            # Vérifier la cohérence avec les autres (en excluant soi-même)
            others = [k for k in self._store.list_items() if k.id != knowledge.id]
            warnings = self._validator.check_consistency(knowledge, others)
            if warnings:
                for w in warnings:
                    self._logger.warning(f"Knowledge consistency warning on update: {w}")

            # Sauvegarder la mise à jour
            updated = self._store.update(knowledge)
            if not updated:
                return False

            # Mettre à jour l'index
            self._indexer.update(knowledge)

            # Mettre à jour le cache
            self._cache.set(f"knowledge:{knowledge.id}", knowledge)
            self._invalidate_query_cache()

            # Incrémenter la version est déjà dans l'objet knowledge
            self._logger.debug(f"Knowledge updated: {knowledge.id}")
            return True

    def set_status(self, knowledge_id: str, target: KnowledgeStatus,
                   actor: str, reason: Optional[str] = None) -> Optional[KnowledgeItem]:
        """
        Fait passer une connaissance au statut demandé (VOLET 05, chapitre 03).

        La transition est refusée si le cycle de vie ne la permet pas. Chaque
        passage est enregistré dans `metadata["status_history"]` : le chapitre
        exige de conserver l'historique de revue et de tracer les révisions.

        Args:
            knowledge_id: identifiant de la connaissance
            target: statut visé
            actor: qui opère la transition — jamais déduit, toujours fourni
            reason: motif, obligatoire pour un retrait ou un archivage

        Returns:
            La connaissance dans son nouveau statut, ou None si elle n'existe pas.

        Raises:
            InvalidStatusTransition: si la transition n'est pas permise
            ValueError: si l'acteur est vide, ou si un motif est requis et absent
        """
        if not actor or not actor.strip():
            raise ValueError("L'acteur d'une transition de statut est obligatoire")

        retraits = (KnowledgeStatus.ARCHIVED, KnowledgeStatus.DEPRECATED)
        if target in retraits and not (reason and reason.strip()):
            raise ValueError(f"Un motif est obligatoire pour passer en {target.value}")

        with self._lock:
            existing = self._store.get(knowledge_id)
            if not existing:
                return None

            check_transition(existing.status, target)

            # Une transition est une révision : nouvelle version, contenu inchangé.
            nouveau = copy.deepcopy(existing)
            nouveau.status = target
            nouveau.version = existing.version + 1
            nouveau.updated_at = datetime.datetime.now(datetime.timezone.utc)
            nouveau.metadata.setdefault("status_history", []).append({
                "from": existing.status.value,
                "to": target.value,
                "actor": actor,
                "reason": reason,
                "at": nouveau.updated_at.isoformat(),
            })

            if not self.update_knowledge(nouveau):
                return None
            self._logger.info(
                f"Knowledge {knowledge_id}: {existing.status.value} -> {target.value} by {actor}"
            )
            return nouveau

    def governance_report(self) -> Dict[str, Any]:
        """
        Rapporte l'état de la gouvernance des connaissances (chapitre 06).

        Returns:
            Par domaine utilisé : le nombre de connaissances, leur répartition
            par statut et le propriétaire déclaré ; plus les domaines sans
            propriétaire et le nombre de connaissances non classées.
        """
        with self._lock:
            return governance_report(self._store)

    def quality_report(self) -> Dict[str, Any]:
        """
        Rapporte les métriques de qualité mesurables (chapitre 09).

        Returns:
            Complétude, fraîcheur, taux de doublons et couverture de validation,
            plus les métriques que la plateforme ne sait pas calculer et la
            raison de chacune.
        """
        with self._lock:
            return quality_report(self._store)

    def list_due_for_revalidation(self, max_age_days: Optional[int] = None,
                                  limit: int = 100) -> List[KnowledgeItem]:
        """
        Liste les connaissances approuvées dont l'approbation a vieilli.

        Répond à l'étape 5 du processus de revue du chapitre 04 (« periodic
        revalidation ») : sans cette liste, une connaissance approuvée une fois
        reste approuvée indéfiniment.

        Args:
            max_age_days: âge maximal accepté ; par défaut, la valeur configurée
                par `GALSEN_KNOWLEDGE_REVALIDATION_DAYS` (180 jours).
            limit: nombre maximal de connaissances examinées

        Returns:
            Les connaissances à remettre en revue, des plus anciennes approbations
            aux plus récentes.
        """
        with self._lock:
            approuvees = self._store.list_items(limit=limit, status=KnowledgeStatus.APPROVED)
            a_revoir = [k for k in approuvees if is_due_for_revalidation(k, max_age_days)]
            return sorted(a_revoir, key=lambda k: k.updated_at)

    def delete_knowledge(self, knowledge_id: str) -> bool:
        """
        Supprime une connaissance.

        Returns:
            True si la suppression a réussi, False sinon
        """
        with self._lock:
            # Vérifier l'existence
            if not self._store.get(knowledge_id):
                return False

            # Supprimer du stockage
            deleted = self._store.delete(knowledge_id)
            if not deleted:
                return False

            # Supprimer de l'index
            self._indexer.delete(knowledge_id)

            # Supprimer du graphe
            self._graph.remove_node(knowledge_id)

            # Supprimer du cache
            self._cache.delete(f"knowledge:{knowledge_id}")
            self._invalidate_query_cache()

            self._logger.debug(f"Knowledge deleted: {knowledge_id}")
            return True

    def search_knowledge(self, query: str, limit: int = 10,
                         role: Optional[str] = None) -> List[KnowledgeItem]:
        """
        Recherche des connaissances par texte.

        Args:
            query: texte recherché
            limit: nombre maximum de résultats
            role: rôle de l'appelant. Sans rôle, seules les connaissances
                publiques sont retournées (chapitre 07).

        Returns:
            Liste de connaissances pertinentes
        """
        with self._lock:
            results = []
            for knowledge, score in self._search_index(query, limit):
                if not can_read(role, knowledge):
                    continue
                results.append(knowledge)
                # Incrémenter le compteur d'accès pour chaque résultat
                self._increment_access_count(knowledge.id)
            return results

    def search_knowledge_with_scores(
        self, query: str, limit: int = 10, role: Optional[str] = None
    ) -> List[Tuple[KnowledgeItem, float]]:
        """
        Recherche des connaissances en conservant leur score de pertinence.

        Args:
            query: Texte recherché
            limit: Nombre maximum de résultats

        Returns:
            Les couples (connaissance, score), du plus pertinent au moins pertinent.
            Le score vient de l'indexeur : c'est la proportion des termes de la
            requête présents dans le document, jamais une valeur déduite du rang.
        """
        with self._lock:
            results: List[Tuple[KnowledgeItem, float]] = []
            for knowledge, score in self._search_index(query, limit):
                if not can_read(role, knowledge):
                    continue
                results.append((knowledge, score))
                self._increment_access_count(knowledge.id)
            return results

    def retrieve_for_prompt(self, prompt: str, max_items: int = 5,
                            statuses: Optional[Iterable[KnowledgeStatus]] = None,
                            role: Optional[str] = None) -> List[KnowledgeItem]:
        """
        Récupère des connaissances pertinentes pour enrichir un prompt (RAG).

        Applique l'étape 5 du pipeline du chapitre 05 : ce qui a été retiré de
        l'usage — archivé ou déprécié — ne nourrit pas un raisonnement, et ce que
        l'appelant n'a pas le droit de lire ne lui est pas retourné.

        Args:
            prompt: la requête
            max_items: nombre maximum de connaissances retournées
            statuses: statuts explicitement acceptés (par exemple, approuvés
                seulement). Par défaut, tout sauf les statuts retirés.
            role: rôle de l'appelant (chapitre 07). Sans rôle, seules les
                connaissances publiques sont retournées — le défaut d'un contrôle
                d'accès est le refus.

        Returns:
            Liste de connaissances à inclure dans le contexte
        """
        with self._lock:
            autorises = frozenset(statuses) if statuses is not None else None
            # Élargir la recherche avant filtrage : sinon un résultat retiré
            # consomme une place et la réponse rend moins que demandé.
            results = self._retrieve_relevant(prompt, max_items * 3)
            # Extraire juste les connaissances (sans les scores)
            knowledge_items = [
                item for item, _ in results
                if is_retrievable(item, autorises) and can_read(role, item)
            ][:max_items]
            # Incrémenter les compteurs d'accès
            for kid in [k.id for k in knowledge_items]:
                self._increment_access_count(kid)
            return knowledge_items

    def retrieve_reliable(self, prompt: str, max_items: int = 5,
                          min_priority: Optional[KnowledgePriority] = None,
                          min_confidence: float = 0.5,
                          statuses: Optional[Iterable[KnowledgeStatus]] = None,
                          role: Optional[str] = None) -> Dict[str, Any]:
        """
        Récupère uniquement des connaissances fiables pour une requête.

        Applique la hiérarchie de fiabilité du chapitre 04 de la Constitution :
        seules les connaissances dont la priorité est suffisamment bonne
        (<= min_priority) et dont la confiance dépasse le seuil sont retournées.
        Les connaissances retirées de l'usage sont écartées avant ce calcul ;
        `statuses` permet d'exiger un statut précis, par exemple l'approbation.

        Returns:
            Dictionnaire contenant :
            - "items": liste des connaissances fiables
            - "reliable": True si au moins une connaissance fiable existe
            - "best_priority": nom de la meilleure priorité trouvée
            - "best_confidence": meilleure confiance trouvée
            - "reason": explication (en français) du résultat
        """
        with self._lock:
            threshold = min_priority if min_priority is not None else KnowledgePriority.P4
            threshold_value = threshold.value if hasattr(threshold, "value") else int(threshold)
            results = self._retrieve_relevant(prompt, max_items * 3)

            autorises = frozenset(statuses) if statuses is not None else None
            reliable_items = []
            best_priority = 4
            best_confidence = 0.0
            for item, _ in results:
                # Étape 5 du pipeline : ce qui est retiré de l'usage, ou que
                # l'appelant n'a pas le droit de lire, ne sert pas.
                if not is_retrievable(item, autorises) or not can_read(role, item):
                    continue
                priority_value = item.priority.value if hasattr(item.priority, "value") else int(item.priority)
                if priority_value > threshold_value:
                    continue
                if item.confidence < min_confidence:
                    continue
                reliable_items.append(item)
                best_priority = min(best_priority, priority_value)
                best_confidence = max(best_confidence, item.confidence)

            # Trier par priorité (plus fiable d'abord) puis confiance décroissante
            reliable_items.sort(
                key=lambda k: (
                    k.priority.value if hasattr(k.priority, "value") else int(k.priority),
                    -k.confidence,
                )
            )
            reliable_items = reliable_items[:max_items]

            # Incrémenter les compteurs d'accès
            for kid in [k.id for k in reliable_items]:
                self._increment_access_count(kid)

            if reliable_items:
                reason = (
                    f"{len(reliable_items)} connaissance(s) fiable(s) trouvée(s) "
                    f"(priorité maximale requise : {threshold.name})."
                )
            else:
                reason = (
                    "Aucune connaissance fiable disponible pour cette requête. "
                    "GalSen IA doit préférer dire « Je ne sais pas » plutôt que "
                    "de générer une information trompeuse."
                )

            return {
                "items": reliable_items,
                "reliable": len(reliable_items) > 0,
                "best_priority": KnowledgePriority(best_priority).name if reliable_items else None,
                "best_confidence": best_confidence,
                "reason": reason,
            }

    def get_related(self, knowledge_id: str) -> List[KnowledgeItem]:
        """
        Récupère les connaissances liées via le graphe.

        Returns:
            Liste de connaissances liées
        """
        with self._lock:
            neighbor_ids = self._graph.get_neighbors(knowledge_id)
            related = []
            for nid in neighbor_ids:
                knowledge = self._store.get(nid)
                if knowledge:
                    related.append(knowledge)
                    self._increment_access_count(nid)
            return related

    def validate_knowledge(self, knowledge: KnowledgeItem) -> tuple[bool, List[str]]:
        """
        Valide une connaissance avant ajout/mise à jour.

        Returns:
            (est_valide, liste_des_erreurs)
        """
        return self._validator.validate(knowledge)

    def load_from_source(self, source: KnowledgeSource) -> List[str]:
        """
        Charge des connaissances depuis une source externe.

        Returns:
            Liste des IDs des connaissances ajoutées
        """
        with self._lock:
            # Charger les données brutes depuis la source
            raw_items = self._loader.load_from_source(source)
            added_ids = []
            for item in raw_items:
                try:
                    kid = self.add_knowledge(item)
                    added_ids.append(kid)
                except Exception as e:
                    self._logger.error(f"Failed to add knowledge from source {source.location}: {e}")
                    # Continuer avec les autres éléments
            return added_ids

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne des statistiques sur le moteur de connaissances.

        Returns:
            Dictionnaire de statistiques
        """
        with self._lock:
            store_count = self._store.count()
            indexer_stats = getattr(self._indexer, 'get_stats', lambda: {})()
            cache_stats = self._cache.stats()
            graph_nodes = self._graph.get_node_count()
            graph_edges = self._graph.get_edge_count()

            # Statistiques supplémentaires sur le contenu
            all_items = self._store.list_items(limit=10000)
            if all_items:
                avg_length = sum(len(k.content) for k in all_items) / len(all_items)
                avg_confidence = sum(k.confidence for k in all_items) / len(all_items)
                # Distribution par type de contenu
                type_counts: dict[str, int] = {}
                for k in all_items:
                    ct = k.content_type.value if hasattr(k.content_type, 'value') else str(k.content_type)
                    type_counts[ct] = type_counts.get(ct, 0) + 1
            else:
                avg_length = 0
                avg_confidence = 0
                type_counts = {}

            return {
                "store": {
                    "total_items": store_count,
                    "average_content_length": round(avg_length, 2),
                    "average_confidence": round(avg_confidence, 3),
                    "content_type_distribution": type_counts
                },
                "indexer": indexer_stats,
                "cache": cache_stats,
                "graph": {
                    "nodes": graph_nodes,
                    "edges": graph_edges
                },
                "loader_factory": "KnowledgeLoaderFactory"
            }

    def cleanup(self) -> None:
        """Nettoie les ressources."""
        with self._lock:
            self._store.cleanup_expired() if hasattr(self._store, 'cleanup_expired') else None
            self._indexer.clear()
            self._cache.clear()
            self._logger.info("Knowledge manager cleaned up")

    # Méthodes privées d'aide
    def rank_by_confidence(self, knowledge_items: List[KnowledgeItem]) -> List[Tuple[KnowledgeItem, float]]:
        """
        Classe les connaissances par confiance décroissante.

        Args:
            knowledge_items: Liste de connaissances à classer

        Returns:
            Liste de tuples (connaissance, score) triée par score décroissant
        """
        with self._lock:
            return self._ranker.rank_by_confidence(knowledge_items)

    def rank_by_recency(self, knowledge_items: List[KnowledgeItem]) -> List[Tuple[KnowledgeItem, float]]:
        """
        Classe les connaissances par récence décroissante (plus récent en premier).

        Args:
            knowledge_items: Liste de connaissances à classer

        Returns:
            Liste de tuples (connaissance, score) triée par score décroissant
        """
        with self._lock:
            return self._ranker.rank_by_recency(knowledge_items)

    def rank(self, knowledge_items: List[KnowledgeItem], weights: Dict[str, float]) -> List[Tuple[KnowledgeItem, float]]:
        """
        Classe les connaissances selon un poids personnalisé.

        Args:
            knowledge_items: Liste de connaissances à classer
            weights: Dictionnaire des poids {"confidence": 0.3, "recency": 0.3, ...}

        Returns:
            Liste de tuples (connaissance, score) triée par score décroissant
        """
        with self._lock:
            return self._ranker.rank(knowledge_items, weights)

    def rank_by_priority(self, knowledge_items: List[KnowledgeItem]) -> List[Tuple[KnowledgeItem, float]]:
        """
        Classe les connaissances par priorité de fiabilité (P1 d'abord).

        Args:
            knowledge_items: Liste de connaissances à classer

        Returns:
            Liste de tuples (connaissance, score) triée par score décroissant
        """
        with self._lock:
            return self._ranker.rank_by_priority(knowledge_items)

    def _increment_access_count(self, knowledge_id: str) -> None:
        """Incrémente le compteur d'accès pour une connaissance."""
        try:
            knowledge = self._store.get(knowledge_id)
            if knowledge:
                count = knowledge.metadata.get("access_count", 0)
                knowledge.metadata["access_count"] = count + 1
                # Mettre à jour le stockage (cela incrémentera la version)
                self._store.update(knowledge)
                # Mettre à jour le cache
                self._cache.set(f"knowledge:{knowledge_id}", knowledge)
        except Exception as e:
            self._logger.debug(f"Failed to increment access count for {knowledge_id}: {e}")