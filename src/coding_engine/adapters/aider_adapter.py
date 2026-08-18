"""
Adaptateur Aider : modifications ciblées de fichiers (ADR-028).

Aider est un programme en ligne de commande, sous Apache-2.0. Il n'est **pas**
importé comme bibliothèque : il porte sa propre couche de modèles (litellm), sa
propre configuration et sa propre gestion Git, qui feraient doublon avec le
Model Engine et le Router Engine de la plateforme. Il est donc appelé en
sous-processus, et son absence n'empêche rien d'autre de fonctionner.

Ce que ce moteur fait le mieux, vérifié contre son propre mode d'emploi : la
modification ciblée de fichiers désignés, avec sa carte du dépôt pour le
contexte. C'est le rôle que le routeur lui donne.

Les drapeaux employés viennent de la documentation d'options du projet :

    --message      la consigne, puis sortie          --no-stream    sortie non interactive
    --model        modèle litellm                     --no-pretty    pas de couleurs
    --yes-always   aucune question posée              --dry-run      vérification seule
    --file         fichier ajouté au contexte         --test-cmd     commande de test
    --no-auto-commits / --no-dirty-commits : GalSen IA garde la main sur Git
    --no-detect-urls : sans réseau autorisé, aider ne va pas chercher d'URL

Configuration :

    GALSEN_AIDER_BIN   chemin de l'exécutable (défaut : `aider` dans le PATH)
"""

import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional

from src.coding_engine.execution import ProcessResult, run_process
from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.types import (
    CodingCapability,
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
    TestReport,
    UnavailabilityReason,
)
from src.coding_engine.workspace import (
    WorkspaceError,
    confine,
    diff_snapshots,
    git_changes,
    resolve_workspace,
    snapshot,
)

VARIABLE_BINAIRE = "GALSEN_AIDER_BIN"
DELAI_VERSION_SECONDES = 20


class AiderAdapter(CodingEngineAdapter):
    """Appelle `aider` en sous-processus pour des modifications ciblées."""

    engine_id = "aider"
    display_name = "Aider"
    primary_capability = CodingCapability.TARGETED_EDIT
    capabilities = [
        CodingCapability.TARGETED_EDIT,
        CodingCapability.REPOSITORY_EXPLORATION,
        CodingCapability.TEST_EXECUTION,
    ]

    def __init__(self, binary: Optional[str] = None):
        """
        Initialise l'adaptateur.

        Args:
            binary: Chemin de l'exécutable. Lu dans l'environnement, puis
                cherché dans le PATH, si absent.
        """
        self._binary = binary or os.environ.get(VARIABLE_BINAIRE) or ""

    # ------------------------------------------------------------------
    # Disponibilité
    # ------------------------------------------------------------------

    def _executable(self) -> Optional[str]:
        """Retrouve l'exécutable, ou `None` s'il est introuvable."""
        if self._binary:
            return self._binary if os.path.isfile(self._binary) else shutil.which(self._binary)
        return shutil.which("aider")

    def check_availability(self) -> EngineAvailability:
        """
        Vérifie qu'`aider` est installé et répond.

        Returns:
            L'état du moteur, avec la commande d'installation s'il manque.
        """
        executable = self._executable()
        if not executable:
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.NOT_INSTALLED,
                detail="`aider` est introuvable. Installez-le avec "
                       "`pip install aider-install && aider-install`, ou indiquez "
                       f"son chemin dans {VARIABLE_BINAIRE}.",
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

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------

    def execute(self, task: CodingTask, model: Optional[ModelSpec]) -> CodingTaskResult:
        """
        Confie une modification ciblée à `aider`.

        Args:
            task: La tâche. Ses `files` deviennent le contexte donné au moteur.
            model: Le modèle imposé par la plateforme.

        Returns:
            Le résultat normalisé. Les fichiers rapportés sont ceux **constatés
            sur le disque**, pas ceux qu'aider dit avoir touchés.
        """
        debut = time.time()
        executable = self._executable()
        if not executable:
            return CodingTaskResult.unavailable(
                self.engine_id, task.id, self.check_availability().detail
            )
        if model is None:
            return CodingTaskResult.unavailable(
                self.engine_id, task.id,
                "Aucun modèle disponible. Aider ne choisit pas de modèle de "
                "lui-même : configurez un fournisseur GalSen IA.",
            )

        try:
            espace = resolve_workspace(task.workspace)
            fichiers = [str(confine(espace, f).relative_to(espace)) for f in task.files]
        except WorkspaceError as erreur:
            return CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id=self.engine_id,
                task_id=task.id, summary=str(erreur), errors=[str(erreur)],
                execution_time_seconds=time.time() - debut,
            )

        avant = snapshot(espace)
        argv, variables = self._commande(executable, task, model, fichiers)
        sortie = run_process(
            argv, cwd=espace, timeout_seconds=task.timeout_seconds,
            extra_environment=variables,
        )

        return self._normaliser(task, model, espace, avant, sortie, debut)

    def _commande(
        self,
        executable: str,
        task: CodingTask,
        model: ModelSpec,
        fichiers: List[str],
    ) -> tuple:
        """
        Construit la ligne de commande et les variables à fournir au moteur.

        Les variables ne sont pas fusionnées ici avec l'environnement hérité :
        c'est le bac à sable qui compose les deux, à partir de sa liste blanche.

        Returns:
            Le couple (arguments, variables fournies).
        """
        nom_modele, variables, options_modele = _traduire_modele(model)

        argv = [
            executable,
            "--model", nom_modele,
            "--message", task.instruction,
            "--yes-always",
            # GalSen IA garde la main sur Git : un commit automatique
            # empêcherait l'appelant de relire avant d'enregistrer.
            "--no-auto-commits",
            "--no-dirty-commits",
            # Sortie non interactive, lisible par un programme.
            "--no-stream",
            "--no-pretty",
            "--no-fancy-input",
            "--no-check-update",
            "--no-show-release-notes",
            "--no-analytics",
            # Le moteur ne doit pas proposer de commandes shell à exécuter :
            # l'exécution de commandes passe par la plateforme, pas par lui.
            "--no-suggest-shell-commands",
            # Aider crée sinon un `.gitignore` de son cru, qui apparaîtrait
            # dans les fichiers modifiés comme s'il venait de la tâche.
            "--no-gitignore",
        ]
        argv += options_modele

        if not task.allow_network:
            # Sans cela, aider va chercher toute URL trouvée dans la consigne.
            argv.append("--no-detect-urls")
        if task.dry_run:
            argv.append("--dry-run")

        commande_de_test = task.metadata.get("test_command")
        if commande_de_test:
            argv += ["--test-cmd", str(commande_de_test), "--auto-test"]

        for fichier in fichiers:
            argv += ["--file", fichier]

        return argv, variables

    def _normaliser(
        self,
        task: CodingTask,
        model: ModelSpec,
        espace,
        avant: Dict[str, Any],
        sortie: ProcessResult,
        debut: float,
    ) -> CodingTaskResult:
        """Traduit la sortie d'aider en résultat GalSen IA."""
        changements = git_changes(espace)
        if changements is None:
            changements = diff_snapshots(avant, snapshot(espace))

        changements = [c for c in changements if not _appartient_a_aider(c.path)]
        avertissements: List[str] = []
        panne_de_modele = _panne_de_modele(sortie.stdout)

        if sortie.timed_out:
            statut = CodingStatus.TIMEOUT
            resume = f"Aider n'a pas terminé en {task.timeout_seconds} s."
        elif not sortie.started:
            statut = CodingStatus.UNAVAILABLE
            resume = sortie.error
        elif panne_de_modele:
            # Vérifié contre le programme réel : aider sort en **code 0** même
            # quand le modèle n'a jamais répondu. Se fier au code de sortie
            # ferait passer une exécution sans aucun travail pour une réussite.
            statut = CodingStatus.UNAVAILABLE
            resume = panne_de_modele
        elif sortie.exit_code == 0:
            statut = CodingStatus.SUCCESS
            resume = _resume(sortie.stdout) or "Aider a terminé."
            if not changements and not task.dry_run:
                avertissements.append(
                    "Aider a terminé sans modifier aucun fichier."
                )
        else:
            statut = CodingStatus.FAILURE
            resume = _resume(sortie.stderr) or f"Aider a échoué (code {sortie.exit_code})."

        erreurs = []
        if statut in (CodingStatus.FAILURE, CodingStatus.TIMEOUT, CodingStatus.UNAVAILABLE):
            erreurs = [erreur for erreur in (resume, sortie.stderr) if erreur]

        return CodingTaskResult(
            status=statut,
            engine_id=self.engine_id,
            task_id=task.id,
            summary=resume,
            files_changed=changements,
            tests=_rapport_de_test(task, sortie),
            errors=erreurs,
            warnings=avertissements,
            execution_time_seconds=time.time() - debut,
            model=model,
            raw_metadata=sortie.to_dict(),
        )


# ----------------------------------------------------------------------
# Traduction du modèle
# ----------------------------------------------------------------------

def _traduire_modele(model: ModelSpec) -> tuple:
    """
    Traduit un `ModelSpec` GalSen dans la convention d'Aider.

    Aider passe par litellm : le modèle s'écrit `fournisseur/nom`, et l'adresse
    du service se donne par variable d'environnement ou par option. Chaque
    fournisseur GalSen a sa correspondance ; un fournisseur inconnu est passé
    tel quel plutôt que remplacé par un défaut, car un défaut silencieux
    enverrait la tâche vers un autre modèle que celui demandé.

    Returns:
        Le triplet (nom pour aider, variables d'environnement, options).
    """
    variables: Dict[str, str] = {}
    options: List[str] = []

    if model.provider_id == "local":
        # Ollama. Le mode d'emploi d'aider recommande `ollama_chat/` plutôt
        # que `ollama/` pour les modèles de discussion.
        nom = f"ollama_chat/{model.model_name}"
        variables["OLLAMA_API_BASE"] = model.base_url or "http://127.0.0.1:11434"
    elif model.provider_id == "openai_compatible":
        nom = f"openai/{model.model_name}"
        if model.base_url:
            options += ["--openai-api-base", model.base_url]
    else:
        nom = (
            model.model_name if "/" in model.model_name
            else f"{model.provider_id}/{model.model_name}"
        )
        if model.base_url:
            options += ["--openai-api-base", model.base_url]

    if model.api_key_env:
        cle = os.environ.get(model.api_key_env)
        if cle:
            # La clé est passée par l'environnement, jamais en argument : une
            # ligne de commande est visible de toute la machine.
            variables["OPENAI_API_KEY"] = cle
    return nom, variables, options


# ----------------------------------------------------------------------
# Lecture de la sortie
# ----------------------------------------------------------------------

_MOTIF_TESTS = re.compile(r"(\d+) passed(?:.*?(\d+) failed)?", re.IGNORECASE)


# Signatures d'échec de modèle relevées dans la sortie réelle d'aider 0.86 :
# litellm y écrit ses erreurs sans faire sortir aider en erreur.
_SIGNATURES_DE_PANNE = (
    ("litellm.APIConnectionError", "le service de modèle n'a pas répondu"),
    ("Connection refused", "connexion refusée par le service de modèle"),
    ("litellm.AuthenticationError", "identifiants refusés par le service de modèle"),
    ("litellm.RateLimitError", "quota du service de modèle atteint"),
    ("litellm.NotFoundError", "modèle inconnu du service"),
    ("litellm.Timeout", "le service de modèle a expiré"),
)

# Fichiers de service d'aider : son historique de discussion et son cache. Les
# rapporter comme fichiers modifiés attribuerait à la tâche des écritures qui
# n'en viennent pas.
_PREFIXES_AIDER = (".aider",)


def _appartient_a_aider(chemin: str) -> bool:
    """Dit si un fichier est un artefact de service d'aider, pas un résultat."""
    # Git rapporte un dossier non suivi avec une barre finale
    # (`.aider.tags.cache.v4/`) : sans la retirer, le nom extrait est vide.
    nom = chemin.rstrip("/").rsplit("/", 1)[-1]
    return nom.startswith(_PREFIXES_AIDER)


def _panne_de_modele(sortie: str) -> str:
    """
    Cherche dans la sortie la trace d'un modèle qui n'a jamais répondu.

    Cette lecture est nécessaire parce que le code de sortie d'aider ne la
    porte pas : vérifié contre aider 0.86.2, une exécution dont chaque appel au
    modèle échoue se termine en code 0. Sans cette détection, la plateforme
    annoncerait une réussite pour une exécution qui n'a rien fait.

    Args:
        sortie: La sortie standard d'aider.

    Returns:
        Le motif en clair, ou une chaîne vide si aucune panne n'est visible.
    """
    for signature, motif in _SIGNATURES_DE_PANNE:
        if signature in (sortie or ""):
            return f"Aider n'a pas pu travailler : {motif}."
    return ""


def _resume(texte: str) -> str:
    """Retient la dernière ligne utile d'une sortie, comme résumé."""
    lignes = [ligne.strip() for ligne in (texte or "").splitlines() if ligne.strip()]
    return lignes[-1][:300] if lignes else ""


def _rapport_de_test(task: CodingTask, sortie: ProcessResult) -> Optional[TestReport]:
    """
    Construit un rapport de tests, **seulement** si des tests ont tourné.

    Sans commande de test demandée, aucun test n'a eu lieu : rendre un rapport
    vide ferait passer une exécution non vérifiée pour une réussite.
    """
    commande = task.metadata.get("test_command")
    if not commande:
        return None

    correspondance = _MOTIF_TESTS.search(sortie.stdout or "")
    reussis = int(correspondance.group(1)) if correspondance else None
    echoues = (
        int(correspondance.group(2))
        if correspondance and correspondance.group(2) else None
    )
    return TestReport(
        command=str(commande),
        passed=reussis,
        failed=echoues,
        exit_code=sortie.exit_code,
        output_excerpt=sortie.stdout[-1000:] if sortie.stdout else "",
    )
