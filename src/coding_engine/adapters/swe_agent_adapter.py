"""
Adaptateur SWE-agent : résolution de problème à partir d'un rapport (ADR-028).

SWE-agent est sous MIT. Comme Aider, il est appelé en **sous-processus** et non
importé : il porte son propre agent, sa propre boucle d'outils et sa propre
couche de modèles, qui feraient doublon avec l'Agent Runtime et le Model Engine.

Ce que ce moteur fait le mieux, vérifié dans sa documentation : partir d'un
énoncé de problème — une issue, un rapport de bogue — et travailler à l'échelle
du dépôt pour le résoudre. C'est le rôle que le routeur lui donne.

Les drapeaux employés viennent de sa documentation en ligne de commande :

    sweagent run
        --agent.model.name=<fournisseur/modèle>
        --agent.model.api_base=<adresse>
        --agent.model.api_key=<clé>
        --agent.model.per_instance_cost_limit=0   (obligatoire hors litellm public)
        --agent.model.total_cost_limit=0
        --agent.model.max_input_tokens=0
        --env.repo.path=<dépôt local>
        --problem_statement.text=<énoncé>

Les trois limites à zéro ne sont pas une commodité : la documentation du projet
les impose pour un modèle auto-hébergé, faute de quoi le calcul de coût, qui
s'appuie sur le registre litellm public, fait échouer l'exécution.

**Limite connue et documentée** : SWE-agent exécute l'agent dans un
environnement conteneurisé. Sans Docker, l'exécution échoue — l'adaptateur le
dit dans son motif d'indisponibilité au lieu de laisser l'appelant deviner.

Configuration :

    GALSEN_SWE_AGENT_BIN   chemin de l'exécutable (défaut : `sweagent`)
"""

import json
import os
import shutil
import time
from typing import Dict, Optional

from src.coding_engine.execution import ProcessResult, run_process
from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.types import (
    CodingCapability,
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
    UnavailabilityReason,
)
from src.coding_engine.workspace import (
    WorkspaceError,
    diff_snapshots,
    git_changes,
    resolve_workspace,
    snapshot,
)

VARIABLE_BINAIRE = "GALSEN_SWE_AGENT_BIN"
DELAI_VERSION_SECONDES = 30

# Clé passée quand le service n'en demande pas : la documentation du projet
# précise qu'elle est exigée par litellm mais peut être arbitraire.
CLE_FACTICE = "galsen-local"


class SweAgentAdapter(CodingEngineAdapter):
    """Appelle `sweagent run` en sous-processus pour résoudre un problème."""

    engine_id = "swe_agent"
    display_name = "SWE-agent"
    primary_capability = CodingCapability.ISSUE_RESOLUTION
    capabilities = [
        CodingCapability.ISSUE_RESOLUTION,
        CodingCapability.REPOSITORY_EXPLORATION,
        CodingCapability.SHELL_EXECUTION,
        CodingCapability.TARGETED_EDIT,
    ]

    def __init__(self, binary: Optional[str] = None):
        """
        Initialise l'adaptateur.

        Args:
            binary: Chemin de l'exécutable `sweagent`.
        """
        self._binary = binary or os.environ.get(VARIABLE_BINAIRE) or ""

    def _executable(self) -> Optional[str]:
        """Retrouve l'exécutable, ou `None`."""
        if self._binary:
            return self._binary if os.path.isfile(self._binary) else shutil.which(self._binary)
        return shutil.which("sweagent")

    def check_availability(self) -> EngineAvailability:
        """
        Vérifie que `sweagent` est installé, et que Docker est là.

        Returns:
            L'état du moteur. L'absence de Docker est signalée comme une
            infrastructure manquante, pas comme une panne du moteur : les deux
            appellent des gestes différents.
        """
        executable = self._executable()
        if not executable:
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.NOT_INSTALLED,
                detail="`sweagent` est introuvable. Installez-le avec "
                       "`pip install sweagent`, ou indiquez son chemin dans "
                       f"{VARIABLE_BINAIRE}.",
                capabilities=self.capabilities,
            )

        if not shutil.which("docker"):
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.MISSING_INFRASTRUCTURE,
                detail="`sweagent` est installé mais Docker est absent. "
                       "SWE-agent exécute l'agent dans un conteneur ; sans "
                       "Docker l'exécution échouerait au démarrage.",
                capabilities=self.capabilities,
            )

        sortie = run_process(
            [executable, "--version"], cwd=os.getcwd(),
            timeout_seconds=DELAI_VERSION_SECONDES,
        )
        if not sortie.ok:
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.NOT_CONFIGURED,
                detail=f"`{executable} --version` a échoué : "
                       f"{sortie.stderr or sortie.error or sortie.stdout}",
                capabilities=self.capabilities,
            )

        return EngineAvailability(
            engine_id=self.engine_id, available=True,
            version=sortie.stdout.strip().splitlines()[0] if sortie.stdout.strip() else None,
            capabilities=self.capabilities,
        )

    def execute(self, task: CodingTask, model: Optional[ModelSpec]) -> CodingTaskResult:
        """
        Confie un énoncé de problème à SWE-agent.

        Args:
            task: La tâche ; son instruction est l'énoncé du problème.
            model: Le modèle imposé par la plateforme.

        Returns:
            Le résultat normalisé, avec les fichiers réellement modifiés.
        """
        debut = time.time()
        etat = self.check_availability()
        if not etat.available:
            return CodingTaskResult.unavailable(self.engine_id, task.id, etat.detail)
        if model is None:
            return CodingTaskResult.unavailable(
                self.engine_id, task.id,
                "Aucun modèle disponible. SWE-agent ne choisit pas de modèle "
                "de lui-même : configurez un fournisseur GalSen IA.",
            )

        try:
            espace = resolve_workspace(task.workspace)
        except WorkspaceError as erreur:
            return CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id=self.engine_id,
                task_id=task.id, summary=str(erreur), errors=[str(erreur)],
                execution_time_seconds=time.time() - debut,
            )

        avant = snapshot(espace)
        argv, variables = self._commande(self._executable(), task, model, espace)
        sortie = run_process(
            argv, cwd=espace, timeout_seconds=task.timeout_seconds,
            extra_environment=variables,
        )
        return self._normaliser(task, model, espace, avant, sortie, debut)

    def _commande(self, executable: str, task: CodingTask, model: ModelSpec, espace) -> tuple:
        """Construit la ligne de commande et les variables d'environnement."""
        nom, cle, variables = _traduire_modele(model)

        argv = [
            executable, "run",
            f"--agent.model.name={nom}",
            # Les trois limites à zéro sont exigées pour un modèle
            # auto-hébergé : le calcul de coût s'appuie sur le registre
            # litellm public, absent pour ces modèles.
            "--agent.model.per_instance_cost_limit=0",
            "--agent.model.total_cost_limit=0",
            "--agent.model.max_input_tokens=0",
            f"--env.repo.path={espace}",
            f"--problem_statement.text={task.instruction}",
        ]
        if model.base_url:
            argv.append(f"--agent.model.api_base={model.base_url}")
        if cle:
            # SWE-agent lit aussi la clé dans l'environnement ; on privilégie
            # cette voie pour ne pas l'écrire dans une ligne de commande.
            variables["OPENAI_API_KEY"] = cle
        else:
            argv.append(f"--agent.model.api_key={CLE_FACTICE}")

        argv += [str(option) for option in task.metadata.get("extra_args", [])]
        return argv, variables

    def _normaliser(
        self, task: CodingTask, model: ModelSpec, espace,
        avant: Dict, sortie: ProcessResult, debut: float,
    ) -> CodingTaskResult:
        """Traduit la sortie de SWE-agent en résultat GalSen IA."""
        changements = git_changes(espace)
        if changements is None:
            changements = diff_snapshots(avant, snapshot(espace))

        if sortie.timed_out:
            statut, resume = CodingStatus.TIMEOUT, (
                f"SWE-agent n'a pas terminé en {task.timeout_seconds} s."
            )
        elif not sortie.started:
            statut, resume = CodingStatus.UNAVAILABLE, sortie.error
        elif sortie.exit_code == 0:
            statut = CodingStatus.SUCCESS
            resume = _resume_de_la_sortie(sortie.stdout) or "SWE-agent a terminé."
        else:
            statut = CodingStatus.FAILURE
            resume = (
                _resume_de_la_sortie(sortie.stderr)
                or f"SWE-agent a échoué (code {sortie.exit_code})."
            )

        erreurs = (
            [e for e in (resume, sortie.stderr) if e]
            if statut is not CodingStatus.SUCCESS else []
        )
        return CodingTaskResult(
            status=statut, engine_id=self.engine_id, task_id=task.id,
            summary=resume, files_changed=changements, errors=erreurs,
            execution_time_seconds=time.time() - debut, model=model,
            raw_metadata=sortie.to_dict(),
        )


def _traduire_modele(model: ModelSpec) -> tuple:
    """
    Traduit un `ModelSpec` GalSen dans la convention de SWE-agent.

    Le projet exige la forme `fournisseur/modèle` et documente `ollama/…` pour
    un serveur local. Aucun modèle par défaut n'est choisi ici.

    Returns:
        Le triplet (nom, clé éventuelle, variables d'environnement).
    """
    variables: Dict[str, str] = {}
    if model.provider_id == "local":
        nom = f"ollama/{model.model_name}"
    elif "/" in model.model_name:
        nom = model.model_name
    else:
        nom = f"openai/{model.model_name}"

    cle = os.environ.get(model.api_key_env) if model.api_key_env else None
    return nom, cle, variables


def _resume_de_la_sortie(texte: str) -> str:
    """
    Retient l'information la plus utile d'une sortie de SWE-agent.

    Le projet écrit des lignes JSON quand il le peut ; sinon on retombe sur la
    dernière ligne non vide.
    """
    lignes = [ligne.strip() for ligne in (texte or "").splitlines() if ligne.strip()]
    for ligne in reversed(lignes):
        if ligne.startswith("{"):
            try:
                charge = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            for cle in ("summary", "submission", "result", "message"):
                if charge.get(cle):
                    return str(charge[cle])[:300]
    return lignes[-1][:300] if lignes else ""
