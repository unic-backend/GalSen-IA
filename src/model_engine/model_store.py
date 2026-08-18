"""
Stockage en mémoire pour le moteur de modèles GalSen IA.
"""

import threading
from typing import List, Dict, Optional
from .types import ModelItem, ModelStatus
from .interfaces import ModelStore
import time


class InMemoryModelStore(ModelStore):
    """Implémentation en mémoire du stockage de modèles."""

    def __init__(self):
        """Initialise le stockage en mémoire."""
        self._models: Dict[str, ModelItem] = {}
        self._lock = threading.RLock()
        self._indexes: Dict[str, Dict[str, List[str]]] = {
            "model_type": {},
            "provider": {},
            "status": {}
        }

    def save(self, model: ModelItem) -> str:
        """Sauvegarde un modèle et retourne son ID."""
        with self._lock:
            # Mettre à jour la timestamp
            model.updated_at = time.time()

            # Stocker le modèle
            self._models[model.model_id] = model

            # Mettre à jour les index
            self._update_indexes(model)

            return model.model_id

    def get(self, model_id: str) -> Optional[ModelItem]:
        """Récupère un modèle par son ID."""
        with self._lock:
            return self._models.get(model_id)

    def update(self, model: ModelItem) -> bool:
        """Met à jour un modèle existant."""
        with self._lock:
            if model.model_id not in self._models:
                return False

            # Mettre à jour la timestamp
            model.updated_at = time.time()

            # Mettre à jour le modèle
            self._models[model.model_id] = model

            # Mettre à jour les index
            self._update_indexes(model)

            return True

    def delete(self, model_id: str) -> bool:
        """Supprime un modèle."""
        with self._lock:
            if model_id not in self._models:
                return False

            model = self._models.pop(model_id)

            # Supprimer des index
            self._remove_from_indexes(model)

            return True

    def list_items(self, limit: int = 100, **filters) -> List[ModelItem]:
        """Liste les modèles avec filtres optionnels."""
        with self._lock:
            models = list(self._models.values())

            # Appliquer les filtres
            if filters:
                filtered_models = []
                for model in models:
                    match = True
                    for key, value in filters.items():
                        if key == "model_type":
                            if model.model_type.value != value:
                                match = False
                                break
                        elif key == "provider":
                            if model.provider != value:
                                match = False
                                break
                        elif key == "status":
                            if model.status.value != value:
                                match = False
                                break
                        elif key == "priority":
                            if model.priority.value != value:
                                match = False
                                break
                        elif hasattr(model, key):
                            if getattr(model, key) != value:
                                match = False
                                break
                        else:
                            match = False
                            break
                    if match:
                        filtered_models.append(model)
                models = filtered_models

            # Trier par date de mise à jour (plus récent en premier)
            models.sort(key=lambda x: x.updated_at, reverse=True)

            # Limiter les résultats
            return models[:limit]

    def cleanup_expired(self) -> int:
        """Nettoie les modèles expirés et retourne le nombre supprimé."""
        # Pour l'implémentation en mémoire, nous ne supprimons pas basé sur l'expiration
        # sauf si explícitement marqué comme expiré
        with self._lock:
            expired_count = 0
            expired_ids = []

            for model_id, model in self._models.items():
                # Exemple de critères d'expiration (peut être personnalisé)
                if model.status == ModelStatus.DEPRECATED:
                    expired_ids.append(model_id)

            for model_id in expired_ids:
                model = self._models.pop(model_id)
                self._remove_from_indexes(model)
                expired_count += 1

            return expired_count

    def _update_indexes(self, model: ModelItem) -> None:
        """Met à jour les index pour un modèle."""
        # Index par type de modèle
        model_type_key = model.model_type.value
        if model_type_key not in self._indexes["model_type"]:
            self._indexes["model_type"][model_type_key] = []
        if model.model_id not in self._indexes["model_type"][model_type_key]:
            self._indexes["model_type"][model_type_key].append(model.model_id)

        # Index par provider
        provider_key = model.provider
        if provider_key not in self._indexes["provider"]:
            self._indexes["provider"][provider_key] = []
        if model.model_id not in self._indexes["provider"][provider_key]:
            self._indexes["provider"][provider_key].append(model.model_id)

        # Index par statut
        status_key = model.status.value
        if status_key not in self._indexes["status"]:
            self._indexes["status"][status_key] = []
        if model.model_id not in self._indexes["status"][status_key]:
            self._indexes["status"][status_key].append(model.model_id)

    def _remove_from_indexes(self, model: ModelItem) -> None:
        """Supprime un modèle des index."""
        # Supprimer de l'index par type de modèle
        model_type_key = model.model_type.value
        if model_type_key in self._indexes["model_type"]:
            if model.model_id in self._indexes["model_type"][model_type_key]:
                self._indexes["model_type"][model_type_key].remove(model.model_id)

        # Supprimer de l'index par provider
        provider_key = model.provider
        if provider_key in self._indexes["provider"]:
            if model.model_id in self._indexes["provider"][provider_key]:
                self._indexes["provider"][provider_key].remove(model.model_id)

        # Supprimer de l'index par statut
        status_key = model.status.value
        if status_key in self._indexes["status"]:
            if model.model_id in self._indexes["status"][status_key]:
                self._indexes["status"][status_key].remove(model.model_id)