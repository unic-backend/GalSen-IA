"""
Types du Coding Engine (ADR-028).

Trois moteurs externes — OpenHands, Aider, SWE-agent — rendent des résultats de
formes totalement différentes : du JSON pour l'un, un diff Git pour l'autre, du
texte pour le troisième. Ce module définit **la forme que GalSen IA leur
impose**, pour que le reste de la plateforme n'ait jamais à connaître lequel a
travaillé.

La règle qui gouverne tous ces types : **aucun champ n'est rempli par
politesse**. Un moteur qui ne rapporte pas les tests laisse `tests` à `None`, il
ne renvoie pas « 0 test échoué ». Zéro test échoué et « je ne sais pas » sont
deux informations différentes, et les confondre ferait passer une exécution non
vérifiée pour une réussite.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CodingStatus(Enum):
    """État final d'une tâche de codage."""

    SUCCESS = "success"
    FAILURE = "failure"
    # Le moteur n'est pas installé, pas joignable, ou pas configuré. Distinct
    # d'un échec : il n'y a rien à corriger dans la demande.
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    REQUIRES_APPROVAL = "requires_approval"


class CodingCapability(Enum):
    """
    Ce qu'un moteur sait faire.

    Le routeur choisit par capacité, jamais par nom de moteur : c'est ce qui
    permet d'ajouter un quatrième moteur sans toucher au routeur.
    """

    # Modifier des fichiers désignés selon une consigne précise.
    TARGETED_EDIT = "targeted_edit"
    # Mener une implémentation en plusieurs étapes, avec itération.
    AUTONOMOUS_IMPLEMENTATION = "autonomous_implementation"
    # Partir d'un rapport de bogue ou d'une issue et remonter à la cause.
    ISSUE_RESOLUTION = "issue_resolution"
    # Lancer les tests du dépôt et réagir à leur résultat.
    TEST_EXECUTION = "test_execution"
    # Exécuter des commandes arbitraires dans l'espace de travail.
    SHELL_EXECUTION = "shell_execution"
    # Travailler à l'échelle du dépôt plutôt que sur des fichiers nommés.
    REPOSITORY_EXPLORATION = "repository_exploration"


class UnavailabilityReason(Enum):
    """Pourquoi un moteur ne peut pas travailler."""

    NOT_INSTALLED = "not_installed"
    NOT_CONFIGURED = "not_configured"
    UNREACHABLE = "unreachable"
    NO_MODEL = "no_model"
    DISABLED = "disabled"
    MISSING_INFRASTRUCTURE = "missing_infrastructure"


@dataclass(frozen=True)
class ModelSpec:
    """
    Le modèle qu'un moteur doit utiliser, dans les termes de GalSen IA.

    Chaque adaptateur traduit cette description dans la convention de son
    moteur — `ollama_chat/x` pour Aider, `ollama/x` pour SWE-agent,
    `fournisseur/modèle` pour OpenHands. **Aucun adaptateur ne choisit de
    modèle par défaut de lui-même** : c'est la plateforme qui décide, sinon
    l'indépendance vis-à-vis des fournisseurs n'existe que sur le papier.

    Attributes:
        provider_id: Fournisseur GalSen (`local`, `openai_compatible`, …).
        model_name: Nom du modèle chez ce fournisseur.
        base_url: Adresse du service, quand il est auto-hébergé.
        api_key_env: **Nom** de la variable d'environnement portant la clé.
            Jamais la clé elle-même : ce type traverse les journaux d'audit.
    """

    provider_id: str
    model_name: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la description, sans jamais exposer de secret."""
        donnees = {"provider_id": self.provider_id, "model_name": self.model_name}
        if self.base_url:
            donnees["base_url"] = self.base_url
        if self.api_key_env:
            donnees["api_key_env"] = self.api_key_env
        return donnees


@dataclass(frozen=True)
class FileChange:
    """
    Un fichier touché par une exécution.

    Attributes:
        path: Chemin relatif à l'espace de travail.
        change_type: `created`, `modified` ou `deleted`.
        insertions: Lignes ajoutées, si le moteur les rapporte.
        deletions: Lignes retirées, si le moteur les rapporte.
    """

    path: str
    change_type: str
    insertions: Optional[int] = None
    deletions: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le changement."""
        donnees: Dict[str, Any] = {"path": self.path, "change_type": self.change_type}
        if self.insertions is not None:
            donnees["insertions"] = self.insertions
        if self.deletions is not None:
            donnees["deletions"] = self.deletions
        return donnees


@dataclass(frozen=True)
class TestReport:
    """
    Ce qu'une exécution de tests a donné.

    N'existe que si des tests ont réellement tourné. Un moteur qui n'en lance
    pas laisse `CodingTaskResult.tests` à `None` — inventer « 0 échec » ferait
    passer une exécution non vérifiée pour une réussite.

    Attributes:
        command: La commande exécutée.
        passed: Tests réussis.
        failed: Tests échoués.
        exit_code: Code de sortie de la commande.
        output_excerpt: Extrait borné de la sortie.
    """

    command: str
    passed: Optional[int] = None
    failed: Optional[int] = None
    exit_code: Optional[int] = None
    output_excerpt: str = ""

    @property
    def ok(self) -> bool:
        """Vrai si la commande de test s'est terminée sans échec."""
        return self.exit_code == 0

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le rapport."""
        return {
            "command": self.command,
            "passed": self.passed,
            "failed": self.failed,
            "exit_code": self.exit_code,
            "ok": self.ok,
            "output_excerpt": self.output_excerpt,
        }


@dataclass(frozen=True)
class CodingTask:
    """
    Une demande de travail logiciel adressée au Coding Engine.

    Attributes:
        instruction: Ce qui est demandé, en clair.
        workspace: Dossier de travail. Rien ne sera lu ni écrit dehors.
        files: Fichiers désignés, quand la demande en vise.
        engine_id: Moteur imposé ; sinon le routeur choisit.
        capabilities: Capacités exigées ; sert au routeur.
        timeout_seconds: Borne d'exécution. Toujours finie.
        dry_run: Vérifie sans laisser le moteur écrire, quand il le permet.
        allow_network: Autorise le moteur à sortir sur le réseau.
        allow_push: Autorise une publication distante ; passe par approbation.
        request_id: Identifiant de la requête appelante, pour l'audit.
        user_id: Sujet à qui l'exécution est imputée.
        metadata: Données libres transmises à l'adaptateur.
    """

    instruction: str
    workspace: str
    files: List[str] = field(default_factory=list)
    engine_id: Optional[str] = None
    capabilities: List[CodingCapability] = field(default_factory=list)
    timeout_seconds: int = 900
    dry_run: bool = False
    allow_network: bool = False
    allow_push: bool = False
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"code_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la tâche pour l'audit."""
        return {
            "id": self.id,
            "instruction": self.instruction,
            "workspace": self.workspace,
            "files": list(self.files),
            "engine_id": self.engine_id,
            "capabilities": [c.value for c in self.capabilities],
            "timeout_seconds": self.timeout_seconds,
            "dry_run": self.dry_run,
            "allow_network": self.allow_network,
            "allow_push": self.allow_push,
            "request_id": self.request_id,
            "user_id": self.user_id,
        }


@dataclass(frozen=True)
class EngineAvailability:
    """
    L'état d'un moteur, avec de quoi agir quand il manque.

    Attributes:
        engine_id: Identifiant du moteur.
        available: Vrai s'il peut travailler maintenant.
        reason: Pourquoi il ne le peut pas.
        detail: Le motif en clair, avec le geste qui répare.
        version: Version détectée, quand le moteur la donne.
        capabilities: Ce qu'il sait faire.
    """

    engine_id: str
    available: bool
    reason: Optional[UnavailabilityReason] = None
    detail: str = ""
    version: Optional[str] = None
    capabilities: List[CodingCapability] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'état."""
        return {
            "engine_id": self.engine_id,
            "available": self.available,
            "reason": self.reason.value if self.reason else None,
            "detail": self.detail,
            "version": self.version,
            "capabilities": [c.value for c in self.capabilities],
        }


@dataclass(frozen=True)
class CodingTaskResult:
    """
    Le résultat normalisé d'une exécution, quel que soit le moteur.

    Attributes:
        status: État final.
        engine_id: Moteur ayant travaillé, ou tenté.
        task_id: Tâche concernée.
        summary: Ce qui a été fait, en une phrase.
        files_changed: Fichiers touchés.
        tests: Rapport de tests, ou `None` si aucun n'a tourné.
        errors: Erreurs rencontrées.
        warnings: Avertissements.
        execution_time_seconds: Durée réelle.
        audit_id: Événement d'audit associé.
        approval_request_id: Demande d'approbation associée.
        model: Modèle utilisé, sans secret.
        raw_metadata: Ce que le moteur a rendu, borné, pour le diagnostic.
    """

    status: CodingStatus
    engine_id: str
    task_id: str
    summary: str = ""
    files_changed: List[FileChange] = field(default_factory=list)
    tests: Optional[TestReport] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    audit_id: Optional[str] = None
    approval_request_id: Optional[str] = None
    model: Optional[ModelSpec] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        """Vrai seulement si le moteur a réellement abouti."""
        return self.status is CodingStatus.SUCCESS

    @classmethod
    def unavailable(
        cls,
        engine_id: str,
        task_id: str,
        detail: str,
        **extras: Any,
    ) -> "CodingTaskResult":
        """
        Construit un résultat d'indisponibilité portant son motif.

        Args:
            engine_id: Moteur concerné.
            task_id: Tâche concernée.
            detail: Le motif, avec le geste qui répare.
            **extras: Champs supplémentaires du résultat.

        Returns:
            Le résultat, jamais un succès de façade.
        """
        return cls(
            status=CodingStatus.UNAVAILABLE,
            engine_id=engine_id,
            task_id=task_id,
            summary=detail,
            errors=[detail],
            **extras,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat pour l'API et l'audit."""
        return {
            "status": self.status.value,
            "ok": self.ok,
            "engine_id": self.engine_id,
            "task_id": self.task_id,
            "summary": self.summary,
            "files_changed": [f.to_dict() for f in self.files_changed],
            "tests": self.tests.to_dict() if self.tests else None,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "execution_time_seconds": round(self.execution_time_seconds, 3),
            "audit_id": self.audit_id,
            "approval_request_id": self.approval_request_id,
            "model": self.model.to_dict() if self.model else None,
            "raw_metadata": dict(self.raw_metadata),
        }
