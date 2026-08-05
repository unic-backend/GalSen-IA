"""
Validateur de connaissances pour le moteur de connaissances GalSen IA.
"""

from typing import List, Tuple
from .types import KnowledgeItem, KnowledgeSource, SourceCategory, KnowledgePriority
from .interfaces import KnowledgeValidator
import re
from datetime import datetime, timezone


class KnowledgeValidatorImpl(KnowledgeValidator):
    """Implémentation du validateur de connaissances."""

    def __init__(self):
        """Initialise le validateur avec des règles de base."""
        # Expressions régulières pour détecter du contenu potentiellement problématique
        self._spam_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        ]  # simple URL detection for spam check

    def validate(self, knowledge: KnowledgeItem) -> tuple[bool, List[str]]:
        """
        Valide une connaissance.
        Retourne (est_valide, liste_des_erreurs).

        Règles de validation:
        - Contenu non vide
        - Longueur raisonnable (entre 10 et 100000 caractères)
        - Langue supportée
        - Type de contenu valide
        - Score de confiance entre 0 et 1
        - Pas de contenu pratiquement du spam (ex: seulement des URLs)
        """
        errors = []

        # 1. Contenu non vide
        if not knowledge.content or not knowledge.content.strip():
            errors.append("Content is empty")

        # 2. Longueur raisonnable
        content_length = len(knowledge.content.strip())
        if content_length < 10:
            errors.append("Content too short (minimum 10 characters)")
        if content_length > 100000:
            errors.append("Content too long (maximum 100,000 characters)")

        # 3. Langue supportée
        if not isinstance(knowledge.language, str):
            try:
                # Si c'est un enum, convertir
                lang_str = knowledge.language.value if hasattr(knowledge.language, 'value') else str(knowledge.language)
            except Exception:
                lang_str = str(knowledge.language)
        else:
            lang_str = knowledge.language

        # Vérifier si la langue est dans notre énumération (on accepte toute chaîne pour l'extensibilité)
        # Mais on pourrait alerter si non reconnue
        known_langs = {l.value for l in __import__('src.knowledge_engine.types', fromlist=['Language']).Language}
        if lang_str not in known_langs:
            # Avertissement mais pas d'erreur - on accepte les nouvelles langues
            pass

        # 4. Type de contenu valide
        if not isinstance(knowledge.content_type, str):
            try:
                ct_str = knowledge.content_type.value if hasattr(knowledge.content_type, 'value') else str(knowledge.content_type)
            except Exception:
                ct_str = str(knowledge.content_type)
        else:
            ct_str = knowledge.content_type

        known_cts = {c.value for c in __import__('src.knowledge_engine.types', fromlist=['ContentType']).ContentType}
        if ct_str not in known_cts:
            errors.append(f"Invalid content type: {ct_str}")

        # 5. Score de confiance entre 0 et 1
        if not (0.0 <= knowledge.confidence <= 1.0):
            errors.append(f"Confidence must be between 0.0 and 1.0, got {knowledge.confidence}")

        # 6. Vérification anti-spam simple
        # Si le contenu contient plus de 50% d'URLs, considérer comme spam
        if knowledge.content:
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                              knowledge.content)
            if len(urls) > 0 and (sum(len(u) for u in urls) / len(knowledge.content)) > 0.5:
                errors.append("Content appears to be mostly URLs (possible spam)")

        # 7. Vérifier que le résumé (s'il existe) n'est pas plus long que le contenu
        if knowledge.summary and len(knowledge.summary) > len(knowledge.content):
            errors.append("Summary cannot be longer than content")

        # 8. Vérifier les dates
        now = datetime.now(timezone.utc)
        if knowledge.created_at > now:
            errors.append("Created date cannot be in the future")
        if knowledge.updated_at > now:
            errors.append("Updated date cannot be in the future")
        if knowledge.updated_at < knowledge.created_at:
            errors.append("Updated date cannot be earlier than created date")

        # 9. La source doit être une instance de KnowledgeSource
        if not isinstance(knowledge.source, KnowledgeSource):
            errors.append(f"Invalid source: {knowledge.source!r}. Must be a KnowledgeSource.")

        # 10. Traçabilité : les connaissances P1/P2 exigent une source traçable
        priority_value = knowledge.priority.value if hasattr(knowledge.priority, "value") else (
            knowledge.priority if isinstance(knowledge.priority, int) else None)
        if priority_value is not None and priority_value <= 2:
            src = knowledge.source
            if (src is None or not src.id or src.id == "unknown"
                    or not src.location or src.location == "unknown"):
                errors.append("P1/P2 knowledge requires a traceable source "
                              "(id and location must be defined)")

        # 11. Catégorie de source et date de récupération valides
        if isinstance(knowledge.source, KnowledgeSource):
            if (knowledge.source.source_category is not None
                    and not isinstance(knowledge.source.source_category, SourceCategory)):
                errors.append(
                    f"Invalid source_category: {knowledge.source.source_category!r}. "
                    "Must be a SourceCategory or None."
                )
            if (knowledge.source.retrieved_at is not None
                    and not isinstance(knowledge.source.retrieved_at, datetime)):
                errors.append(
                    f"Invalid retrieved_at: {knowledge.source.retrieved_at!r}. "
                    "Must be a datetime or None."
                )

        # 12. La priorité doit être un niveau de priorité valide
        if not isinstance(knowledge.priority, KnowledgePriority):
            errors.append(
                f"Invalid priority: {knowledge.priority!r}. Must be a KnowledgePriority."
            )

        return (len(errors) == 0, errors)

    def check_consistency(self, knowledge: KnowledgeItem,
                          existing: List[KnowledgeItem]) -> List[str]:
        """
        Vérifie la cohérence avec les connaissances existantes.
        Retourne une liste d'avertissements (pas d'erreur bloquante).

        Vérifications:
        - Détection de duplication basée sur le hash de contenu
        - Conflits de versions
        """
        warnings = []
        content_hash = knowledge.compute_content_hash()

        for existing_item in existing:
            # Ignorer la comparaison avec soi-même
            if existing_item.id == knowledge.id:
                continue

            # Vérifier la duplication exacte de contenu
            if existing_item.compute_content_hash() == content_hash:
                warnings.append(
                    f"Content is identical to existing knowledge ID {existing_item.id} "
                    f"(version {existing_item.version})"
                )

                # Avertir si le doublon porte une priorité différente
                existing_priority = (existing_item.priority.value
                                     if hasattr(existing_item.priority, "value") else None)
                new_priority = (knowledge.priority.value
                                if hasattr(knowledge.priority, "value") else None)
                if existing_priority is not None and new_priority is not None \
                        and existing_priority != new_priority:
                    warnings.append(
                        f"Content identical to knowledge ID {existing_item.id} but "
                        f"with different priority ({existing_item.priority.name} "
                        f"vs {knowledge.priority.name})"
                    )

            # Vérifier les conflits de titre/summary approximatif (optionnel)
            # Pour simplifier, on ne fait rien d'autre ici

        return warnings