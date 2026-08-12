"""
Stockage en mémoire des connaissances pour le moteur de connaissances GalSen IA.
"""

from typing import Dict, List, Optional
from .types import KnowledgeItem
from .interfaces import KnowledgeStore
import copy
import threading
import datetime


class InMemoryKnowledgeStore(KnowledgeStore):
    """Stockage en mémoire des connaissances."""

    def __init__(self):
        """Initialise le stockage."""
        self._data: Dict[str, KnowledgeItem] = {}
        self._lock = threading.RLock()
        self._logger = None  # sera injecté si nécessaire

    def save(self, knowledge: KnowledgeItem) -> str:
        """Sauvegarde une connaissance et retourne son ID."""
        with self._lock:
            # S'assurer que l'ID existe
            if not knowledge.id:
                knowledge.id = knowledge.compute_content_hash()
                knowledge.id = f"kn{knowledge.id[:12]}"

            # Vérifier si une version plus récente existe déjà
            existing = self._data.get(knowledge.id)
            if existing and existing.version >= knowledge.version:
                # Ne pas écraser une version plus récente ou égale
                return existing.id

            # Sauvegarder
            self._data[knowledge.id] = knowledge
            return knowledge.id

    def get(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """Récupère une connaissance par son ID.

        Une **copie** est retournée, comme le fait déjà le magasin SQLite qui
        désérialise à chaque lecture. Rendre la référence interne rendait
        `update()` inutilisable depuis le flux normal — lire, corriger,
        enregistrer : incrémenter la version de l'objet lu incrémentait du même
        coup celle du magasin, si bien que le contrôle `version > existante`
        refusait la mise à jour. Deux implémentations d'une même interface ne
        peuvent pas diverger sur ce point sans qu'un appelant correct sur l'une
        soit fautif sur l'autre.
        """
        with self._lock:
            knowledge = self._data.get(knowledge_id)
            return copy.deepcopy(knowledge) if knowledge is not None else None

    def update(self, knowledge: KnowledgeItem) -> bool:
        """Met à jour une connaissance existante."""
        with self._lock:
            if knowledge.id not in self._data:
                return False
            # S'assurer que la version est plus récente
            existing = self._data[knowledge.id]
            if knowledge.version <= existing.version:
                return False
            self._data[knowledge.id] = knowledge
            return True

    def record_access(self, knowledge_id: str) -> int:
        """Compte une consultation et retourne le nouveau total."""
        with self._lock:
            knowledge = self._data.get(knowledge_id)
            if knowledge is None:
                return 0
            total = int(knowledge.metadata.get("access_count", 0)) + 1
            knowledge.metadata["access_count"] = total
            return total

    def record_accesses(self, knowledge_ids) -> int:
        """Compte plusieurs consultations d'un coup ; retourne le nombre mis à jour."""
        from collections import Counter

        touchees = 0
        with self._lock:
            for identifiant, nombre in Counter(knowledge_ids).items():
                knowledge = self._data.get(identifiant)
                if knowledge is None:
                    continue
                knowledge.metadata["access_count"] = (
                    int(knowledge.metadata.get("access_count", 0)) + nombre
                )
                touchees += 1
        return touchees

    def delete(self, knowledge_id: str) -> bool:
        """Supprime une connaissance."""
        with self._lock:
            if knowledge_id in self._data:
                del self._data[knowledge_id]
                return True
            return False

    def list_items(self, limit: int = 100, **filters) -> List[KnowledgeItem]:
        """Liste les connaissances avec filtres optionnels."""
        with self._lock:
            results = []
            for knowledge in self._data.values():
                match = True
                for key, value in filters.items():
                    if key == "knowledge_type":
                        if knowledge.knowledge_type.value != value:
                            match = False
                            break
                    elif key == "content_type":
                        if knowledge.content_type.value != value:
                            match = False
                            break
                    elif key == "language":
                        if knowledge.language.value != value:
                            match = False
                            break
                    elif key == "domain":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.domain.value != wanted:
                            match = False
                            break
                    elif key == "sensitivity":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.sensitivity.value != wanted:
                            match = False
                            break
                    elif key == "status":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.status.value != wanted:
                            match = False
                            break
                    elif key == "tags":
                        if isinstance(value, str):
                            if value not in knowledge.tags:
                                match = False
                                break
                        elif isinstance(value, list):
                            if not all(tag in knowledge.tags for tag in value):
                                match = False
                                break
                    elif key == "categories":
                        if isinstance(value, str):
                            if value not in knowledge.categories:
                                match = False
                                break
                        elif isinstance(value, list):
                            if not all(cat in knowledge.categories for cat in value):
                                match = False
                                break
                    elif key == "source_type":
                        if knowledge.source.type != value:
                            match = False
                            break
                    elif key == "min_confidence":
                        if knowledge.confidence < float(value):
                            match = False
                            break
                    elif key == "max_confidence":
                        if knowledge.confidence > float(value):
                            match = False
                            break
                    elif key == "priority":
                        wanted = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current != wanted:
                            match = False
                            break
                    elif key == "min_priority":
                        # "Au moins aussi fiable que" : on garde les priorités <= la valeur
                        minimum = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current > minimum:
                            match = False
                            break
                    elif key == "max_priority":
                        # "Au plus aussi fiable que" : on garde les priorités >= la valeur
                        maximum = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current < maximum:
                            match = False
                            break
                    elif key == "source_category":
                        wanted = value.value if hasattr(value, "value") else value
                        sc = knowledge.source.source_category
                        current = sc.value if sc is not None else "unknown"
                        if current != wanted:
                            match = False
                            break
                    elif key == "created_after":
                        if knowledge.created_at < datetime.datetime.fromisoformat(value):
                            match = False
                            break
                    elif key == "created_before":
                        if knowledge.created_at > datetime.datetime.fromisoformat(value):
                            match = False
                            break
                if match:
                    results.append(knowledge)
                    if len(results) >= limit:
                        break
            return results

    def count(self, **filters) -> int:
        """
        Compte les connaissances correspondant aux filtres.

        Le compte n'est jamais plafonné : il portait auparavant la limite de
        10 000 de `list_items`, si bien qu'un magasin de 10 050 éléments en
        rapportait 10 000 sans le dire. Un compte faux est pire qu'un compte
        absent — rien ne permet de s'en apercevoir.
        """
        if not filters:
            with self._lock:
                return len(self._data)
        return len(self.list_items(limit=len(self._data), **filters))

    def cleanup_old_versions(self, keep_latest: int = 1) -> int:
        """Nettoie les anciennes versions, en gardant seulement les plus récentes.
        Pour cet entrepôt en mémoire simple, nous ne gardons qu'une seule version par ID.
        Retourne le nombre d'éléments supprimés (toujours 0 dans cette implémentation).
        """
        # Dans cette implémentation simple, nous ne stockons qu'une seule version par ID
        # (la plus récente sauvegardée). Donc rien à nettoyer.
        return 0