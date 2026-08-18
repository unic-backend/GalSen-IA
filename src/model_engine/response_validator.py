"""
Validateur de réponses pour le moteur de modèles GalSen IA.
"""

from typing import Any, Optional, Dict
from .types import ModelItem
from .interfaces import ResponseValidator
import re


class BasicResponseValidator(ResponseValidator):
    """
    Validateur de réponses de base qui vérifie la validité structurale
    et détecte certains patterns d'hallucination évidents.
    """

    def __init__(self):
        """Initialise le validateur de réponses."""
        # Patterns indiquant potentiellement une hallucination ou une réponse non fondée
        self._hallucination_indicators = [
            r"je ne sais pas",
            r"i don't know",
            r"je ne suis pas sûr",
            r"i am not sure",
            r"selon certaines sources non vérifiées",
            r"according to unverified sources",
            r"il semble que",
            r"it seems that",
            r"on pense que",
            r"it is thought that"
        ]

        # Patterns indiquant une réponse potentiellement hallucinée (spécifique à certains domaines)
        self._medical_hallucination_indicators = [
            r"cure miraculeuse",
            r"miracle cure",
            r"traitement secret",
            r"secret treatment",
            r"remède oublié par la médecine",
            r"forgotten cure"
        ]

        self._financial_hallucination_indicators = [
            r"rendement garanti de \d+%",
            r"guaranteed return of \d+%",
            r"stratégie infaillible",
            r"foolproof strategy",
            r"initié confidentiel",
            r"confidential insider"
        ]

    def validate_response(self, model_item: ModelItem, response: Any,
                         expected_format: Optional[Dict[str, Any]] = None) -> bool:
        """
        Valide une réponse selon des critères de base.

        Args:
            model_item: Modèle qui a généré la réponse
            response: Réponse à valider
            expected_format: Format attendu optionnel

        Returns:
            True si la réponse est valide, False sinon
        """
        # Vérifier que la réponse n'est pas None ou vide
        if response is None:
            return False

        # Convertir en string si nécessaire pour les vérifications
        if not isinstance(response, str):
            # Pour les réponses structurées (JSON, etc.), nous pourrions avoir besoin
            # d'une validation différente, mais pour l'instant nous convertissons en string
            response_str = str(response)
        else:
            response_str = response

        # Vérifier que la réponse n'est pas vide ou seulement des espaces
        if not response_str or not response_str.strip():
            return False

        # Vérifier la longueur minimale (éviter les réponses trop courtes qui pourraient être des erreurs)
        if len(response_str.strip()) < 3:
            return False

        # Si un format attendu est spécifié, valider contre celui-ci
        if expected_format:
            return self._validate_against_format(response, expected_format)

        # Vérifications de base supplémentaires
        # Par exemple, vérifier que la réponse ne contient pas clairement d'erreur
        error_indicators = ["error:", "exception:", "traceback", "failed to", "échec"]
        if any(indicator in response_str.lower() for indicator in error_indicators):
            # Cependant, certaines réponses légitimes peuvent contenir ces mots
            # Nous ne rejetons donc pas immédiatement, mais nous le notons pour le score d'hallucination
            pass

        return True

    def detect_hallucination(self, model_item: ModelItem, response: Any,
                            context: Optional[str] = None) -> float:
        """
        Détecte les hallucinations potentielles dans une réponse.

        Args:
            model_item: Modèle qui a généré la réponse
            response: Réponse à analyser
            context: Contexte optionnel (question ou matériel source) pour la comparaison

        Returns:
            Score d'hallucination entre 0.0 (probablement pas d'hallucination)
            et 1.0 (fortement indiqué comme hallucination)
        """
        if response is None:
            return 1.0  # Considérer une réponse nulle comme fortement hallucinée

        # Convertir en string pour l'analyse
        if not isinstance(response, str):
            response_str = str(response)
        else:
            response_str = response

        # Score initial
        hallucination_score = 0.0

        # Vérifier les indicateurs généraux d'hallucination
        for pattern in self._hallucination_indicators:
            if re.search(pattern, response_str, re.IGNORECASE):
                hallucination_score += 0.1  # Chaque correspondance augmente légèrement le score

        # Vérifier les indicateurs spécifiques au domaine si le contexte est fourni
        if context:
            context_lower = context.lower()
            if "medical" in context_lower or "health" in context_lower or "santé" in context_lower:
                for pattern in self._medical_hallucination_indicators:
                    if re.search(pattern, response_str, re.IGNORECASE):
                        hallucination_score += 0.3
            elif "financial" in context_lower or "finance" in context_lower or "argent" in context_lower:
                for pattern in self._financial_hallucination_indicators:
                    if re.search(pattern, response_str, re.IGNORECASE):
                        hallucination_score += 0.3

        # Vérifier des réponses excessivement longues qui pourraient être des divagations
        if len(response_str) > 1000:
            # Très longue réponse pourrait être une divagation ou contenir des hallucinations
            hallucination_score += 0.2

        # Vérifier des réponses qui sont trop courtes pour être significatives
        if len(response_str.strip()) < 20:
            # Très courtes réponses pourraient être des hallucinations ou des refus
            hallucination_score += 0.2

        # Normaliser le score entre 0.0 et 1.0
        hallucination_score = min(1.0, max(0.0, hallucination_score))

        return hallucination_score

    def _validate_against_format(self, response: Any,
                                expected_format: Dict[str, Any]) -> bool:
        """
        Valide une réponse contre un format attendu.

        Args:
            response: Réponse à valider
            expected_format: Format attendu

        Returns:
            True si la réponse correspond au format attendu, False sinon
        """
        # Implémentation simple - dans une version réelle, nous utiliserions
        # une bibliothèque comme jsonschema pour la validation JSON
        if isinstance(expected_format, dict) and isinstance(response, dict):
            # Vérifier que tous les champs requis sont présents
            required_fields = expected_format.get("required", [])
            for field in required_fields:
                if field not in response:
                    return False

            # Vérifier les types si spécifiés
            properties = expected_format.get("properties", {})
            for field, expected_type in properties.items():
                if field in response:
                    # Vérification de type très basique
                    if expected_type == "string" and not isinstance(response[field], str):
                        return False
                    elif expected_type == "number" and not isinstance(response[field], (int, float)):
                        return False
                    elif expected_type == "boolean" and not isinstance(response[field], bool):
                        return False
                    elif expected_type == "array" and not isinstance(response[field], list):
                        return False
                    elif expected_type == "object" and not isinstance(response[field], dict):
                        return False

        return True