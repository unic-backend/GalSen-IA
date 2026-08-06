"""
Contrat de la couche de connecteurs externes.

Définit l'interface abstraite `Connector` : le propriétaire, côté plateforme,
d'un système externe. Tout fournisseur (SMTP, API transactionnelle, S3, MinIO)
se branche en implémentant ce contrat, sans que le code appelant change.

Référence : ADR-007, VOLET 02 chapitre 09 (Integration Architecture).
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import ConnectorCheck, ConnectorDescription, ConnectorKind, ConnectorStatus


class Connector(ABC):
    """
    Contrat d'un connecteur vers un système externe.

    Trois questions doivent trouver une réponse sans qu'aucune action métier ne
    soit déclenchée : qui es-tu (`describe`), es-tu configuré (`is_configured`),
    réponds-tu (`check`). C'est ce qui permet d'auditer un déploiement sans
    envoyer d'e-mail ni écrire de fichier.
    """

    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Identifiant stable du connecteur, unique dans le registre."""

    @property
    @abstractmethod
    def kind(self) -> ConnectorKind:
        """Catégorie de système externe que ce connecteur représente."""

    @abstractmethod
    def describe(self) -> ConnectorDescription:
        """
        Décrit le connecteur : rôle, variables d'environnement lues, opérations.

        Ne doit jamais contenir la **valeur** d'un secret, seulement le nom des
        variables consultées (ADR-004).
        """

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Indique si la configuration nécessaire est présente.

        Doit répondre à partir de l'environnement seul, sans appel réseau : un
        déploiement doit pouvoir être audité hors ligne.
        """

    @abstractmethod
    def check(self) -> ConnectorCheck:
        """
        Vérifie que le système externe répond, au coût le plus faible possible.

        Ne lève jamais : un système injoignable est signalé par un statut
        `UNREACHABLE`, des identifiants refusés par `UNAUTHORIZED`.
        """

    # ------------------------------------------------------------------
    # Utilitaires communs aux implémentations
    # ------------------------------------------------------------------
    def _read_environment(self, variable: str) -> Optional[str]:
        """
        Lit une variable d'environnement, en traitant la chaîne vide comme absente.

        Le secret n'est jamais conservé en attribut : il est relu à chaque appel,
        de sorte qu'il ne subsiste pas en mémoire après un changement et qu'il
        n'apparaisse dans aucun état sérialisable du connecteur.
        """
        value = os.environ.get(variable)
        return value if value else None

    def _missing_variables(self, variables: List[str]) -> List[str]:
        """Retourne les variables d'environnement attendues qui sont absentes."""
        return [name for name in variables if self._read_environment(name) is None]

    def _not_configured(self, missing: List[str]) -> ConnectorCheck:
        """Construit le résultat d'une vérification impossible faute de configuration."""
        return ConnectorCheck(
            connector_id=self.connector_id,
            kind=self.kind,
            status=ConnectorStatus.NOT_CONFIGURED,
            detail=(
                "Variables d'environnement absentes : " + ", ".join(missing)
                if missing
                else "Configuration absente."
            ),
        )


class ConnectorRegistryContract(ABC):
    """Contrat du registre : qui connaît les connecteurs de la plateforme."""

    @abstractmethod
    def register(self, connector: Connector) -> None:
        """Enregistre un connecteur ; un identifiant déjà pris est refusé."""

    @abstractmethod
    def get(self, connector_id: str) -> Optional[Connector]:
        """Retourne un connecteur par identifiant, ou None s'il est inconnu."""

    @abstractmethod
    def list_connectors(self, kind: Optional[ConnectorKind] = None) -> List[Connector]:
        """Retourne les connecteurs enregistrés, éventuellement filtrés par catégorie."""

    @abstractmethod
    def check_all(self) -> Dict[str, Any]:
        """Vérifie tous les connecteurs et retourne un rapport agrégé."""
