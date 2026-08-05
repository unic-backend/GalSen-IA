"""
Gestionnaire de contexte pour le moteur de modèles GalSen IA.
"""

from typing import List, Dict, Any
from .types import ModelItem
from .interfaces import ModelContextManager
import re


class SimpleModelContextManager(ModelContextManager):
    """
    Gestionnaire de contexte simple qui tronque l'historique des messages
    pour tenir dans les limites de tokens du modèle.
    """

    def __init__(self):
        """Initialise le gestionnaire de contexte."""
        # Approximation: 1 token ≈ 4 caractères pour l'anglais
        # Ceci est une simplification - dans une implémentation réelle,
        # nous utiliserions le tokenizer réel du modèle
        self._chars_per_token = 4

    def _estimate_tokens(self, text: str) -> int:
        """Estime le nombre de tokens dans un texte."""
        if not text:
            return 0
        # Approximation simple basée sur les caractères
        return len(text) // self._chars_per_token

    def _estimate_message_tokens(self, message: Dict[str, str]) -> int:
        """Estime le nombre de tokens dans un message."""
        # Compter les tokens dans le contenu et le rôle
        content_tokens = self._estimate_tokens(message.get("content", ""))
        role_tokens = self._estimate_tokens(message.get("role", ""))
        # Ajouter quelques tokens pour la structure formatée
        return content_tokens + role_tokens + 5

    def manage_context(self, model_item: ModelItem, messages: List[Dict[str, str]],
                      max_tokens: int) -> List[Dict[str, str]]:
        """
        Gère le contexte pour respecter les limites de tokens.

        Args:
            model_item: Modèle pour lequel gérer le contexte
            messages: Liste des messages de conversation
            max_tokens: Nombre maximum de tokens autorisés

        Returns:
            Liste de messages tronquée si nécessaire
        """
        if not messages:
            return messages

        # Calculer l'utilisation actuelle des tokens
        current_tokens = sum(self._estimate_message_tokens(msg) for msg in messages)

        # Si déjà dans les limites, retourner tel quel
        if current_tokens <= max_tokens:
            return messages

        # Sinon, tronquer en commençant par les messages les plus anciens
        # (en gardant généralement le message système si présent)
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        non_system_messages = [msg for msg in messages if msg.get("role") != "system"]

        # Toujours garder les messages système
        result = list(system_messages)
        remaining_tokens = max_tokens - sum(
            self._estimate_message_tokens(msg) for msg in system_messages
        )

        # Ajouter les messages les plus récents jusqu'à atteindre la limite
        # On parcourt de la fin vers le début pour garder les plus récents
        for message in reversed(non_system_messages):
            message_tokens = self._estimate_message_tokens(message)
            if message_tokens <= remaining_tokens:
                result.insert(len(system_messages), message)  # Insérer après les messages système
                remaining_tokens -= message_tokens
            else:
                # Si ce message ne tient pas, on arrête (on garde les plus récents)
                break

        # S'assurer que l'ordre est correct (système, puis chronologique)
        # Les messages système sont déjà au début
        # Les autres messages sont dans l'ordre original car nous avons inséré à la bonne position
        # mais nous les avons traités en ordre inverse, donc il faut les remettre dans l'ordre
        non_system_in_result = [msg for msg in result if msg.get("role") != "system"]
        non_system_in_result.reverse()  # Remettre dans l'ordre chronologique
        result = system_messages + non_system_in_result

        return result

    def truncate_history(self, messages: List[Dict[str, str]],
                        max_tokens: int) -> List[Dict[str, str]]:
        """
        Tronque l'historique pour tenir dans la limite de tokens.

        Args:
            messages: Liste des messages de conversation
            max_tokens: Nombre maximum de tokens autorisés

        Returns:
            Liste de messages tronquée
        """
        # Cette méthode est similaire à manage_context mais sans modèle spécifique
        # Nous utilisons une limite de tokens générique
        return self._truncate_messages_by_token_count(messages, max_tokens)

    def _truncate_messages_by_token_count(self, messages: List[Dict[str, str]],
                                         max_tokens: int) -> List[Dict[str, str]]:
        """Tronque les messages en comptant les tokens."""
        if not messages:
            return messages

        # Calculer les tokens utilisés
        used_tokens = sum(self._estimate_message_tokens(msg) for msg in messages)

        if used_tokens <= max_tokens:
            return messages

        # Stratégie: garder le premier message (souvent système) et les derniers messages
        # jusqu'à ce que nous atteignions la limite
        result = []
        used_tokens = 0

        # Toujours essayer de garder le premier message s'il existe
        if messages:
            first_msg = messages[0]
            first_tokens = self._estimate_message_tokens(first_msg)
            if first_tokens <= max_tokens:
                result.append(first_msg)
                used_tokens = first_tokens

        # Ajouter les messages depuis la fin jusqu'à ce que nous atteignions la limite
        # (en inversant l'ordre pour garder les plus récents)
        for i in range(len(messages) - 1, 0, -1):  # Commencer à la fin, sauter le premier si déjà ajouté
            msg = messages[i]
            msg_tokens = self._estimate_message_tokens(msg)
            if used_tokens + msg_tokens <= max_tokens:
                # Insérer à la bonne position pour maintenir l'ordre
                if i == 0 or (len(result) > 0 and result[0] != messages[0]):
                    result.insert(0 if len(result) == 0 else 1, msg)
                else:
                    result.append(msg)
                used_tokens += msg_tokens
            else:
                # Si ce message ne tient pas, on continue avec le suivant (plus ancien)
                continue

        # S'assurer que l'ordre est correct
        # Le premier message (s'il était système) doit être en premier
        # Ensuite, les messages dans leur ordre original
        if len(messages) > 0 and len(result) > 0:
            # Trouver l'indice du premier message original dans le résultat
            try:
                first_orig_index = result.index(messages[0]) if messages[0] in result else -1
                if first_orig_index > 0:  # Si ce n'est pas déjà en première position
                    # Le déplacer en première position
                    first_msg = result.pop(first_orig_index)
                    result.insert(0, first_msg)
            except ValueError:
                pass  # Le premier message n'est pas dans le résultat, c'est OK

        return result